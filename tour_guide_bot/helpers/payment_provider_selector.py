from abc import ABC, abstractmethod
from typing import ClassVar, Optional, Sequence

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
)

from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import BaseHandlerCallback
from tour_guide_bot.models.settings import PaymentProvider


class PaymentProviderSelector(BaseHandlerCallback, ABC):
    STATE_SELECT_PAYMENT_PROVIDER: ClassVar[Optional[int]] = -12
    SKIP_PAYMENT_PROVIDER_SELECTION_IF_SINGLE: ClassVar[int] = True

    @abstractmethod
    async def after_payment_provider_selected(
        self,
        provider: PaymentProvider,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_provider: bool,
    ):
        pass

    @abstractmethod
    def get_payment_provider_selection_message(self, language: str) -> str:
        pass

    async def get_acceptable_payment_providers(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> Sequence[PaymentProvider]:
        return (
            await self.db_session.scalars(
                select(PaymentProvider).where(PaymentProvider.enabled == True)
            )
        ).all()

    async def handle_no_payment_provider_found(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)
        await self.edit_or_reply_text(
            update,
            context,
            t(language).pgettext("bot-generic", "No payment providers found."),
        )
        return ConversationHandler.END

    async def send_payment_provider_selector(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        providers: Sequence[
            PaymentProvider
        ] = await self.get_acceptable_payment_providers(update, context)

        if len(providers) == 1 and self.SKIP_PAYMENT_PROVIDER_SELECTION_IF_SINGLE:
            if update.callback_query:
                await update.callback_query.answer()

            return await self.after_payment_provider_selected(
                providers[0], update, context, True
            )

        language = await self.get_language(update, context)

        if len(providers) == 0:
            if update.callback_query:
                await update.callback_query.answer()

            return await self.handle_no_payment_provider_found(update, context)

        keyboard = []

        for provider in providers:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        provider.name,
                        callback_data=self.get_callback_data(
                            "select_provider", provider.id
                        ),
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    t(language).pgettext("bot-generic", "Abort"),
                    callback_data=self.get_callback_data("cancel_provider_selection"),
                )
            ]
        )

        if update.callback_query:
            await update.callback_query.answer()

        await self.edit_or_reply_text(
            update,
            context,
            self.get_payment_provider_selection_message(language),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return self.STATE_SELECT_PAYMENT_PROVIDER

    async def handle_selected_payment_provider(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        provider: PaymentProvider | None = await self.db_session.scalar(
            select(PaymentProvider).where(
                PaymentProvider.id == int(context.matches[0].group(1))
            )
        )

        if update.callback_query:
            await update.callback_query.answer()

        if provider is None:
            await self.edit_or_reply_text(
                update,
                context,
                t(await self.get_language(update, context)).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )

            return ConversationHandler.END

        return await self.after_payment_provider_selected(
            provider, update, context, False
        )

    @classmethod
    def get_select_payment_provider_handlers(cls) -> list:
        return [
            CallbackQueryHandler(
                cls.partial(cls.handle_selected_payment_provider),
                cls.get_callback_data_pattern("select_provider", r"(\d+)"),
            ),
            CallbackQueryHandler(
                cls.partial(
                    cls.cancel
                    if cls.STATE_SELECT_PAYMENT_PROVIDER
                    else cls.cancel_without_conversation
                ),
                cls.get_callback_data_pattern("cancel_provider_selection"),
            ),
        ]
