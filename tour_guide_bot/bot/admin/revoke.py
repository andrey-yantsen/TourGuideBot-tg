import datetime
import re

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import (
    AdminProtectedBaseHandlerCallback,
    get_tour_title,
)
from tour_guide_bot.models.guide import BoughtTours, Guest, Tour


class RevokeCommandHandler(AdminProtectedBaseHandlerCallback):
    STATE_TOUR = 1
    STATE_PHONE_NUMBER = 2
    STATE_REVOKE = 3

    @classmethod
    def get_handlers(cls):
        return [
            ConversationHandler(
                entry_points=[CommandHandler("revoke", cls.partial(cls.start))],
                states={
                    cls.STATE_TOUR: [
                        CallbackQueryHandler(
                            cls.partial(cls.tour), r"^revoke_tour:(\d+)$"
                        ),
                    ],
                    cls.STATE_PHONE_NUMBER: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.phone_number),
                        ),
                        MessageHandler(filters.CONTACT, cls.partial(cls.phone_number)),
                    ],
                    cls.STATE_REVOKE: [
                        CallbackQueryHandler(
                            cls.partial(cls.revoke), r"^revoke_confirm:(\d+)$"
                        ),
                    ],
                },
                fallbacks=[
                    CommandHandler("cancel", cls.partial(cls.cancel)),
                    CallbackQueryHandler(cls.partial(cls.cancel), "cancel"),
                ],
                name="admin-revoke",
                persistent=True,
            )
        ]

    def cleanup_context(self, context: ContextTypes.DEFAULT_TYPE):
        for key in ("phone_number", "tour_id"):
            if key in context.user_data:
                del context.user_data[key]

    async def revoke(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        guest_id = context.user_data.pop("guest_id")
        tour_id = context.user_data.pop("tour_id")

        if tour_id != context.matches[0].group(1):
            await self.edit_or_reply_text(
                update,
                context,
                t(user.language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )
            return ConversationHandler.END

        guest = await self.db_session.scalar(select(Guest).where(Guest.id == guest_id))

        if not guest:
            await self.edit_or_reply_text(
                update,
                context,
                t(user.language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )
            return ConversationHandler.END

        tour = await self.db_session.scalar(
            select(Tour)
            .where(Tour.id == tour_id)
            .options(selectinload(Tour.translation))
        )

        purchase = await self.db_session.scalar(
            select(BoughtTours).where(
                (BoughtTours.guest == guest)
                & (BoughtTours.tour == tour)
                & (BoughtTours.expire_ts >= datetime.datetime.now())
            )
        )

        if not purchase:
            await self.edit_or_reply_text(
                update,
                context,
                t(user.language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )
            return ConversationHandler.END

        purchase.expire_ts = datetime.datetime.now()
        purchase.is_user_notified = True
        self.db_session.add(purchase)
        await self.db_session.commit()

        await self.edit_or_reply_text(
            update,
            context,
            t(user.language)
            .pgettext("admin-revoke", 'Access to "{0}" was revoked from +{1}.')
            .format(get_tour_title(tour, user.language, context), guest.phone),
        )

        return ConversationHandler.END

    async def phone_number(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        if update.message.contact:
            if update.message.contact.phone_number:
                phone_number = update.message.contact.phone_number
            else:
                await update.message.reply_text(
                    t(user.language).pgettext(
                        "admin-generic",
                        "The contact you sent me "
                        "doesn't have a phone number; please try again.",
                    )
                )
                return self.STATE_PHONE_NUMBER
        else:
            phone_number = update.message.text

        phone_number = re.sub(r"\D+", "", phone_number)

        guest = await self.db_session.scalar(
            select(Guest).where(Guest.phone == phone_number)
        )

        if not guest:
            await update.message.reply_text(
                t(user.language).pgettext(
                    "admin-revoke",
                    "I don't see anybody with that phone number in the database; please send another one.",
                )
            )
            return

        tour = await self.db_session.scalar(
            select(Tour)
            .where(Tour.id == context.user_data["tour_id"])
            .options(selectinload(Tour.translation))
        )

        purchase = await self.db_session.scalar(
            select(BoughtTours).where(
                (BoughtTours.guest == guest)
                & (BoughtTours.tour == tour)
                & (BoughtTours.expire_ts >= datetime.datetime.now())
            )
        )

        if not purchase:
            await update.message.reply_text(
                t(user.language).pgettext(
                    "admin-revoke",
                    "This phone number doesn't have access to that tour; aborting.",
                )
            )

            for key in ("phone_number", "tour_id"):
                if key in context.user_data:
                    del context.user_data[key]

            return ConversationHandler.END

        context.user_data["guest_id"] = guest.id

        await update.message.reply_text(
            t(user.language)
            .pgettext(
                "admin-revoke",
                'Are you sure you want to revoke the access to "{0}" from +{1}?',
            )
            .format(get_tour_title(tour, user.language, context), phone_number),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            t(user.language).pgettext("bot-generic", "Yes"),
                            callback_data="revoke_confirm:%d" % (tour.id,),
                        ),
                        InlineKeyboardButton(
                            t(user.language).pgettext("bot-generic", "Abort"),
                            callback_data="cancel",
                        ),
                    ],
                ]
            ),
        )

        return self.STATE_REVOKE

    async def tour(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)
        await update.callback_query.edit_message_text(
            t(user.language).pgettext(
                "admin-revoke",
                "Enter the phone number from which you want to revoke"
                " access to the tour (with country code) or share the contact."
                " Send /cancel at any time if you wish to cancel.",
            )
        )
        context.user_data["tour_id"] = context.matches[0].group(1)
        return self.STATE_PHONE_NUMBER

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        tours = await self.db_session.scalars(
            select(Tour).options(selectinload(Tour.translation))
        )
        keyboard = []

        user = await self.get_user(update, context)
        current_language = user.language

        for tour in tours:
            title = get_tour_title(tour, user.language, context)
            keyboard.append(
                [
                    InlineKeyboardButton(
                        title, callback_data="revoke_tour:%s" % (tour.id,)
                    )
                ]
            )

        if len(keyboard) == 0:
            await update.message.reply_text(
                t(user.language).pgettext(
                    "admin-generic",
                    "Unfortunately, you don't have any tours available for the guests.",
                )
            )
            return ConversationHandler.END

        keyboard.append(
            [
                InlineKeyboardButton(
                    t(current_language).pgettext("bot-generic", "Abort"),
                    callback_data="cancel",
                )
            ]
        )

        await update.message.reply_text(
            t(user.language).pgettext("admin-generic", "Please select the tour."),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return self.STATE_TOUR
