from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
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
from tour_guide_bot.helpers.payment_provider_selector import PaymentProviderSelector
from tour_guide_bot.helpers.telegram import SubcommandHandler
from tour_guide_bot.models.settings import PaymentProvider


class ChangePaymentProvider(SubcommandHandler, PaymentProviderSelector):
    STATE_WAITING_FOR_TOKEN = 1

    @classmethod
    def get_handlers(cls):
        return [
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        cls.partial(cls.send_payment_provider_selector),
                        cls.get_callback_data_pattern(),
                    )
                ],
                states={
                    cls.STATE_SELECT_PAYMENT_PROVIDER: cls.get_select_payment_provider_handlers(),
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

    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-configure", "Change payment token")

    @classmethod
    async def is_available(cls, db_session: AsyncSession) -> bool:
        stmt = select(PaymentProvider).where(PaymentProvider.enabled == True)
        provider: PaymentProvider | None = await db_session.scalar(stmt)
        return provider is not None

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

    def get_payment_provider_selection_message(self, language: str) -> str:
        return t(language).pgettext(
            "admin-configure", "Please select the payment provider you want to update."
        )

    async def after_payment_provider_selected(
        self,
        provider: PaymentProvider,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_provider: bool,
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
            t(lang)
            .pgettext(
                "admin-configure",
                "Please send me the new payment token for {}.",
            )
            .format(provider.name)
        )

        context.user_data["provider_id"] = provider.id

        return self.STATE_WAITING_FOR_TOKEN

    async def set_token(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        lang = await self.get_language(update, context)

        if not await self.is_available(self.db_session):
            await update.message.reply_text(
                t(lang).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                )
            )
            return ConversationHandler.END

        stmt = select(PaymentProvider).where(
            PaymentProvider.id == context.user_data["provider_id"]
        )
        provider: PaymentProvider | None = await self.db_session.scalar(stmt)

        if provider is None or not provider.enabled:
            await update.message.reply_text(
                t(lang).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                )
            )
            return ConversationHandler.END

        provider.config = {"token": update.message.text}
        self.db_session.add(provider)
        await self.db_session.commit()

        await update.message.reply_text(
            t(lang).pgettext(
                "admin-configure",
                "Payment token has been updated.",
            )
        )

        return ConversationHandler.END
