from sqlalchemy import Sequence, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
)

from tour_guide_bot import t
from tour_guide_bot.helpers.payment_provider_selector import PaymentProviderSelector
from tour_guide_bot.helpers.telegram import SubcommandHandler
from tour_guide_bot.models.guide import Product
from tour_guide_bot.models.settings import PaymentProvider


class DeletePaymentProvider(SubcommandHandler, PaymentProviderSelector):
    STATE_SELECT_PAYMENT_PROVIDER = None  # we're not in a conversation

    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-configure", "Delete payment token")

    @classmethod
    def get_handlers(cls):
        return [
            CallbackQueryHandler(
                cls.partial(cls.send_payment_provider_selector),
                cls.get_callback_data_pattern(),
            ),
            CallbackQueryHandler(
                cls.partial(cls.delete_confirm),
                cls.get_callback_data_pattern(r"(\d+)"),
            ),
            CallbackQueryHandler(
                cls.partial(cls.cancel_without_conversation),
                cls.get_callback_data_pattern("cancel_provider_removal"),
            ),
            *cls.get_select_payment_provider_handlers(),
        ]

    @classmethod
    async def is_available(cls, db_session: AsyncSession) -> bool:
        stmt = select(PaymentProvider).where(PaymentProvider.enabled == True)
        provider: PaymentProvider | None = await db_session.scalar(stmt)
        return provider is not None

    def get_payment_provider_selection_message(self, language: str) -> str:
        return t(language).pgettext(
            "admin-configure", "Please select the payment provider you want to delete."
        )

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

        products: Sequence[Product] = await self.db_session.scalars(
            select(Product).where(
                (Product.payment_provider_id == provider.id)
                & (Product.available == True)
            )
        )

        for product in products:
            product.available = False
            self.db_session.add(product)

        await self.db_session.commit()

        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            t(lang).pgettext("admin-configure", "The payment token has been deleted.")
        )

    async def after_payment_provider_selected(
        self,
        provider: PaymentProvider,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_provider: bool,
    ):
        lang = await self.get_language(update, context)

        context.user_data["provider_id"] = provider.id

        msg = (
            t(lang)
            .pgettext(
                "admin-configure",
                "Are you sure you want to delete the payment token {}?",
            )
            .format(provider.name)
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
                            callback_data=self.get_callback_data(
                                "cancel_provider_removal"
                            ),
                        ),
                    ],
                ]
            ),
        )
