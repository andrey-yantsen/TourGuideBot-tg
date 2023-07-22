from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import SubcommandHandler
from tour_guide_bot.models.settings import PaymentProvider


class AddPaymentProvider(SubcommandHandler):
    STATE_WAITING_FOR_NAME = 1
    STATE_WAITING_FOR_TOKEN = 2

    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-configure", "Add payment token")

    @classmethod
    def get_handlers(cls):
        return [
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        cls.partial(cls.payment_token_init),
                        cls.get_callback_data_pattern(),
                    )
                ],
                states={
                    cls.STATE_WAITING_FOR_NAME: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.set_name),
                        ),
                        MessageHandler(
                            filters.ALL & ~filters.COMMAND & ~filters.TEXT,
                            cls.partial(cls.incorrect_message),
                        ),
                    ],
                    cls.STATE_WAITING_FOR_TOKEN: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.set_token),
                        ),
                        MessageHandler(
                            filters.ALL & ~filters.COMMAND & ~filters.TEXT,
                            cls.partial(cls.incorrect_message),
                        ),
                    ],
                },
                fallbacks=[
                    CommandHandler("cancel", cls.partial(cls.cancel)),
                    CallbackQueryHandler(cls.partial(cls.cancel), "cancel"),
                    MessageHandler(filters.COMMAND, cls.partial(cls.unknown_command)),
                    MessageHandler(filters.ALL, cls.partial(cls.unexpected_message)),
                ],
                name="admin-configure-" + cls.__name__.lower(),
                persistent=True,
            )
        ]

    async def incorrect_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        user = await self.get_user(update, context)
        await update.callback_query.edit_message_text(
            t(user.language).pgettext(
                "admin-configure", "Please send me a regular text message."
            )
        )

        return None

    async def payment_token_init(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        lang = await self.get_language(update, context)

        if not await self.is_available(self.db_session):
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                t(lang).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                )
            )
            return

        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            t(lang).pgettext(
                "admin-configure",
                "Please send me the name of the payment provider you want to set up "
                "(this value will be used later for your convenience).",
            )
        )

        return self.STATE_WAITING_FOR_NAME

    async def set_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        lang = await self.get_language(update, context)

        if not await self.is_available(self.db_session):
            await update.message.reply_text(
                t(lang).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                )
            )
            return ConversationHandler.END

        context.user_data["provider_name"] = update.message.text

        await update.message.reply_text(
            t(lang).pgettext(
                "admin-configure",
                "Great! Now send me the payment token.",
            )
        )

        return self.STATE_WAITING_FOR_TOKEN

    async def set_token(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        lang = await self.get_language(update, context)

        if (
            not await self.is_available(self.db_session)
            or "provider_name" not in context.user_data
        ):
            await update.message.reply_text(
                t(lang).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                )
            )
            return ConversationHandler.END

        provider = PaymentProvider(
            name=context.user_data["provider_name"],
            config={"token": update.message.text},
            enabled=True,
        )
        self.db_session.add(provider)
        await self.db_session.commit()
        del context.user_data["provider_name"]

        await update.message.reply_text(
            t(lang).pgettext(
                "admin-configure",
                "Payment provider has been added.",
            )
        )

        return ConversationHandler.END
