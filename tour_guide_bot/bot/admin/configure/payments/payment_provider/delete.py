from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
)

from tour_guide_bot import t
from tour_guide_bot.bot.admin.configure.payments.payment_provider import (
    PaymentProviderBase,
)
from tour_guide_bot.models.settings import PaymentProvider


class DeletePaymentProvider(PaymentProviderBase):
    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-configure", "Delete payment token")

    @classmethod
    def get_handlers(cls):
        return [
            CallbackQueryHandler(
                cls.partial(cls.delete_init),
                cls.get_callback_data_pattern(),
            ),
            CallbackQueryHandler(
                cls.partial(cls.delete_confirm),
                cls.get_callback_data_pattern(r"(\d+)"),
            ),
        ]

    @classmethod
    async def is_available(cls, db_session: AsyncSession) -> bool:
        stmt = select(PaymentProvider).where(PaymentProvider.enabled == True)
        provider: PaymentProvider | None = await db_session.scalar(stmt)
        return provider is not None

    async def delete_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        lang = await self.get_language(update, context)

        stmt = select(PaymentProvider).where(
            PaymentProvider.id == int(context.matches[0].group(1))
        )
        provider: PaymentProvider | None = await self.db_session.scalar(stmt)

        if not provider:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                t(lang).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                )
            )
            return

        provider.enabled = False
        self.db_session.add(provider)
        await self.db_session.commit()

        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            t(lang).pgettext("admin-configure", "The payment token has been deleted.")
        )

    async def delete_init(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        lang = await self.get_language(update, context)

        stmt = select(PaymentProvider).where(PaymentProvider.enabled == True)
        provider: PaymentProvider | None = await self.db_session.scalar(stmt)

        if not provider:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                t(lang).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                )
            )
            return

        msg = t(lang).pgettext(
            "admin-configure", "Are you sure you want to delete the payment token?"
        )

        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            t(lang).pgettext("bot-generic", "Yes"),
                            callback_data=self.get_callback_data(provider.id),
                        ),
                        InlineKeyboardButton(
                            t(lang).pgettext("bot-generic", "Abort"),
                            callback_data="cancel",
                        ),
                    ],
                ]
            ),
        )
