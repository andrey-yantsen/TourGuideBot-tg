import datetime
import re

import dateparser
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


class ApproveCommandHandler(AdminProtectedBaseHandlerCallback):
    STATE_PHONE_NUMBER = 2
    STATE_TOUR = 1
    STATE_DURATION = 3

    @classmethod
    def get_handlers(cls):
        return [
            ConversationHandler(
                entry_points=[CommandHandler("approve", cls.partial(cls.start))],
                states={
                    cls.STATE_TOUR: [
                        CallbackQueryHandler(
                            cls.partial(cls.tour), "^approve_tour:(\d+)$"
                        ),
                    ],
                    cls.STATE_PHONE_NUMBER: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.phone_number),
                        ),
                        MessageHandler(filters.CONTACT, cls.partial(cls.phone_number)),
                    ],
                    cls.STATE_DURATION: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, cls.partial(cls.duration)
                        ),
                    ],
                },
                fallbacks=[
                    CommandHandler("cancel", cls.partial(cls.cancel)),
                    CallbackQueryHandler(cls.partial(cls.cancel), "cancel"),
                ],
                name="admin-approve",
                persistent=True,
            )
        ]

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        for key in ("phone_number", "tour_id"):
            if key in context.user_data:
                del context.user_data[key]

        await self.edit_or_reply_text(
            update, context, t(user.language).pgettext("bot-generic", "Cancelled.")
        )

        return ConversationHandler.END

    async def duration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        d = dateparser.parse(update.message.text)

        now = datetime.datetime.now()

        if not d or d < now:
            await update.message.reply_text(
                t(user.language).pgettext(
                    "admin-approve",
                    "I've failed to parse your input; please try again."
                    ' Enter something like "in 6 months", "in 1 week" and so on.',
                )
            )
            return self.STATE_DURATION

        guest = await self.db_session.scalar(
            select(Guest).where(Guest.phone == context.user_data["phone_number"])
        )
        tour = await self.db_session.scalar(
            select(Tour)
            .where(Tour.id == context.user_data["tour_id"])
            .options(selectinload(Tour.translation))
        )

        if not guest:
            guest = Guest(phone=context.user_data["phone_number"])
            self.db_session.add(guest)

        purchase = BoughtTours(guest=guest, tour=tour, expire_ts=d)
        if guest.id:
            existing_purchase = await self.db_session.scalar(
                select(BoughtTours).where(
                    (BoughtTours.guest == guest)
                    & (BoughtTours.tour == tour)
                    & (BoughtTours.expire_ts >= now)
                )
            )
            if existing_purchase:
                existing_purchase.expire_ts = d
                purchase = existing_purchase

        self.db_session.add(purchase)
        await self.db_session.commit()

        await update.message.reply_text(
            t(user.language)
            .pgettext(
                "admin-approve",
                "Phone number +{0} was approved for the tour '{1}' until {2}.",
            )
            .format(
                guest.phone,
                get_tour_title(tour, user.language, context),
                d.strftime("%Y-%m-%d %H:%M:%S"),
            )
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

        context.user_data["phone_number"] = re.sub("\D+", "", phone_number)

        await update.message.reply_text(
            t(user.language).pgettext(
                "admin-approve",
                'When the access should expire? Enter something like "in 6 months", "in 1 week" and so on.',
            )
        )

        return self.STATE_DURATION

    async def tour(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)
        await update.callback_query.edit_message_text(
            t(user.language).pgettext(
                "admin-approve",
                "Enter the phone number that should be able to"
                " access the tour (with country code), or share the contact."
                " Send /cancel at any time if you want to abort.",
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
                        title, callback_data="approve_tour:%s" % (tour.id,)
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
