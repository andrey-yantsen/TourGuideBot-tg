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
from tour_guide_bot.models.guide import Product


class SelectProductHandler(BaseHandlerCallback, ABC):
    STATE_SELECT_PRODUCT: ClassVar[Optional[int]] = -13
    SKIP_PRODUCT_SELECTION_IF_SINGLE: ClassVar[int] = False

    @abstractmethod
    async def after_product_selected(
        self,
        product: Product,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_product: bool,
    ):
        pass

    @abstractmethod
    async def get_product_selection_message(
        self,
        tour_id: int,
        language: str,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> str:
        pass

    async def get_acceptable_products(
        self,
        tour_id: int,
        language: str,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> Sequence[Product]:
        return (
            await self.db_session.scalars(
                select(Product)
                .where(
                    (Product.tour_id == tour_id)
                    & (Product.available == True)
                    & (Product.language == language)
                )
                .order_by(Product.currency, Product.price)
            )
        ).all()

    async def handle_no_products_found(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)
        await self.edit_or_reply_text(
            update,
            context,
            t(language).pgettext(
                "bot-generic",
                "Unfortunately, the selected tour is not available for purchasing online.",
            ),
        )

        return ConversationHandler.END if self.STATE_SELECT_PRODUCT else None

    async def send_product_selector(
        self,
        tour_id: int,
        language: str,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        products: Sequence[Product] = await self.get_acceptable_products(
            tour_id, language, update, context
        )

        if len(products) == 1 and self.SKIP_PRODUCT_SELECTION_IF_SINGLE:
            if update.callback_query:
                await update.callback_query.answer()

            return await self.after_product_selected(products[0], update, context, True)

        language = await self.get_language(update, context)

        if len(products) == 0:
            if update.callback_query:
                await update.callback_query.answer()

            return await self.handle_no_products_found(update, context)

        keyboard = []

        for product in products:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        await product.formatted_name(language),
                        callback_data=self.get_callback_data(
                            "select_product", product.id
                        ),
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    t(language).pgettext("bot-generic", "Abort"),
                    callback_data=self.get_callback_data("cancel_product_selection"),
                )
            ]
        )

        if update.callback_query:
            await update.callback_query.answer()

        await self.edit_or_reply_text(
            update,
            context,
            await self.get_product_selection_message(tour_id, language, context),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return self.STATE_SELECT_PRODUCT

    async def handle_selected_product(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        product: Product | None = await self.db_session.scalar(
            select(Product).where(Product.id == int(context.matches[0].group(1)))
        )

        if update.callback_query:
            await update.callback_query.answer()

        if product is None or not product.available:
            await self.edit_or_reply_text(
                update,
                context,
                t(await self.get_language(update, context)).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )

            return ConversationHandler.END if self.STATE_SELECT_PRODUCT else None

        return await self.after_product_selected(product, update, context, False)

    @classmethod
    def get_select_product_handlers(cls) -> list:
        return [
            CallbackQueryHandler(
                cls.partial(cls.handle_selected_product),
                cls.get_callback_data_pattern("select_product", r"(\d+)"),
            ),
            CallbackQueryHandler(
                cls.partial(
                    cls.cancel
                    if cls.STATE_SELECT_PRODUCT
                    else cls.cancel_without_conversation
                ),
                cls.get_callback_data_pattern("cancel_product_selection"),
            ),
        ]
