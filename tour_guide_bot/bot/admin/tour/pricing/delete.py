from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
)

from tour_guide_bot import t
from tour_guide_bot.helpers.language_selector import SelectLanguageHandler
from tour_guide_bot.helpers.product_selector import SelectProductHandler
from tour_guide_bot.helpers.telegram import SubcommandHandler, get_tour_title
from tour_guide_bot.helpers.tours_selector import SelectTourHandler
from tour_guide_bot.models.guide import Product, Tour


class DeletePricingHandler(
    SubcommandHandler, SelectTourHandler, SelectLanguageHandler, SelectProductHandler
):
    STATE_SELECT_TOUR = None
    STATE_LANGUAGE_SELECTION = None
    STATE_SELECT_PRODUCT = None

    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-tour", "Delete a product")

    @classmethod
    def get_handlers(cls):
        return [
            CallbackQueryHandler(
                cls.partial(cls.send_tour_selector), cls.get_callback_data_pattern()
            ),
            CallbackQueryHandler(
                cls.partial(cls.delete_product),
                cls.get_callback_data_pattern(r"(\d+)"),
            ),
            CallbackQueryHandler(
                cls.partial(cls.cancel_without_conversation),
                cls.get_callback_data_pattern("cancel"),
            ),
            *cls.get_select_tour_handlers(),
            *cls.get_select_language_handlers(),
            *cls.get_select_product_handlers(),
        ]

    @classmethod
    async def is_available(cls, db_session: AsyncSession) -> bool:
        products_count: int = await db_session.scalar(
            select(func.count(Product.id)).where(Product.available == True)  # noqa
        )
        return products_count > 0

    def get_tour_selection_message(self, language: str) -> str:
        return t(language).pgettext(
            "admin-tours",
            "Please select the tour from which you want to remove a product.",
        )

    def get_language_selection_message(self, user_language: str) -> str:
        return t(user_language).pgettext(
            "admin-tours", "Please select the language you want to update."
        )

    async def get_product_selection_message(
        self,
        tour_id: int,
        language: str,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> str:
        return t(language).pgettext(
            "admin-tours", "Please select the product you want to delete."
        )

    async def after_tour_selected(
        self,
        tour: Tour,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_tour: bool,
    ):
        context.user_data["tour_id"] = tour.id

        return await self.send_language_selector(update, context)

    async def after_language_selected(
        self,
        language: str,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_language: bool,
    ):
        context.user_data["language"] = language
        return await self.send_product_selector(
            context.user_data["tour_id"], language, update, context
        )

    async def after_product_selected(
        self,
        product: Product,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_product: bool,
    ):
        language = await self.get_language(update, context)

        tour: Tour | None = await self.db_session.scalar(
            select(Tour)
            .where(Tour.id == context.user_data["tour_id"])
            .options(selectinload(Tour.translations))
        )

        if tour is None:
            await self.edit_or_reply_text(
                update,
                context,
                t(language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )
            return

        await update.callback_query.edit_message_text(
            t(language)
            .pgettext(
                "admin-tours",
                'Do you really want to delete product "{product}" from the tour "{tour}"?',
            )
            .format(
                product=await product.formatted_name(language),
                tour=get_tour_title(tour, language, context),
            ),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            t(language).pgettext("bot-generic", "Yes"),
                            callback_data=self.get_callback_data(product.id),
                        ),
                        InlineKeyboardButton(
                            t(language).pgettext("bot-generic", "Abort"),
                            callback_data=self.get_callback_data("cancel"),
                        ),
                    ],
                ]
            ),
        )

    async def delete_product(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        language = await self.get_language(update, context)
        product: Product | None = await self.db_session.scalar(
            select(Product)
            .where(Product.id == context.matches[0].group(1))
            .options(selectinload(Product.tour).selectinload(Tour.translations))
        )

        if not product:
            await update.callback_query.answer()
            await self.edit_or_reply_text(
                update,
                context,
                t(language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )
            return

        product.available = False
        self.db_session.add(product)
        await self.db_session.commit()

        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            t(language)
            .pgettext(
                "admin-tours",
                'The product "{product}" was removed from the tour "{tour}".',
            )
            .format(
                product=await product.formatted_name(language),
                tour=get_tour_title(product.tour, language, context),
            )
        )
