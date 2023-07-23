import datetime
import re
from typing import Sequence

from babel.dates import format_datetime
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
from tour_guide_bot.models.guide import Guest, Subscription, Tour


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
                            cls.partial(cls.tour),
                            cls.get_callback_data_pattern("approve_tour", r"(\d+)"),
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
                    CallbackQueryHandler(
                        cls.partial(cls.cancel), cls.get_callback_data_pattern("cancel")
                    ),
                    MessageHandler(filters.COMMAND, cls.partial(cls.unknown_command)),
                    MessageHandler(filters.ALL, cls.partial(cls.unexpected_message)),
                ],
                name="admin-approve",
                persistent=True,
            )
        ]

    def cleanup_context(self, context: ContextTypes.DEFAULT_TYPE):
        for key in ("phone_number", "tour_id"):
            if key in context.user_data:
                del context.user_data[key]

    async def duration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        try:
            d = int(update.message.text)
        except ValueError:
            d = None

        if not d or d <= 0:
            await update.message.reply_text(
                t(user.language).pgettext(
                    "admin-approve",
                    "I've failed to parse your input; please enter a valid positive number.",
                )
            )
            return self.STATE_DURATION

        guest: Guest | None = await self.db_session.scalar(
            select(Guest).where(Guest.phone == context.user_data["phone_number"])
        )
        tour: Tour | None = await self.db_session.scalar(
            select(Tour)
            .where(Tour.id == context.user_data["tour_id"])
            .options(selectinload(Tour.translations))
        )

        if not guest:
            guest = Guest(phone=context.user_data["phone_number"])
            self.db_session.add(guest)

        now = datetime.datetime.now()
        expire_ts = now + datetime.timedelta(days=d)
        purchase = Subscription(guest=guest, tour=tour, expire_ts=expire_ts)
        if guest.id:
            existing_purchase: Subscription | None = await self.db_session.scalar(
                select(Subscription).where(
                    (Subscription.guest == guest)
                    & (Subscription.tour == tour)
                    & (Subscription.expire_ts >= now)
                )
            )
            if existing_purchase:
                existing_purchase.expire_ts = expire_ts
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
                format_datetime(expire_ts, locale=user.language),
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

        context.user_data["phone_number"] = re.sub(r"\D+", "", phone_number)

        await update.message.reply_text(
            t(user.language).pgettext(
                "admin-approve",
                "How long the user should have access? Please enter a duration in days.",
            )
        )

        return self.STATE_DURATION

    async def tour(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)
        await update.callback_query.answer()
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
        tours: Sequence[Tour] = (
            await self.db_session.scalars(
                select(Tour).options(selectinload(Tour.translations))
            )
        ).all()
        keyboard = []

        user = await self.get_user(update, context)
        current_language = user.language

        for tour in tours:
            title = get_tour_title(tour, user.language, context)
            keyboard.append(
                [
                    InlineKeyboardButton(
                        title,
                        callback_data=self.get_callback_data("approve_tour", tour.id),
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
                    callback_data=self.get_callback_data("cancel"),
                )
            ]
        )

        await update.message.reply_text(
            t(user.language).pgettext("admin-generic", "Please select the tour."),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return self.STATE_TOUR
