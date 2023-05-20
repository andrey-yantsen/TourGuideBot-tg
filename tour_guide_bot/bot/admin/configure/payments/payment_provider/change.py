from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)

from tour_guide_bot import t
from tour_guide_bot.bot.admin.configure.payments.payment_provider.add import (
    AddPaymentProvider,
)
from tour_guide_bot.models.settings import PaymentProvider


class ChangePaymentProvider(AddPaymentProvider):
    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-configure", "Change payment token")

    @classmethod
    async def available(cls, db_session: AsyncSession) -> bool:
        stmt = select(PaymentProvider).where(PaymentProvider.enabled == True)
        provider = await db_session.scalar(stmt)
        return provider is not None

    async def payment_token_init(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        lang = await self.get_language(update, context)

        if not await self.available(self.db_session):
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
                "Please send me the new payment token.",
            )
        )

        return self.STATE_WAITING_FOR_TOKEN

    async def set_token(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        lang = await self.get_language(update, context)

        if not await self.available(self.db_session):
            await update.message.reply_text(
                t(lang).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                )
            )
            return ConversationHandler.END

        stmt = select(PaymentProvider).where(PaymentProvider.enabled == True)
        provider = await self.db_session.scalar(stmt)
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
