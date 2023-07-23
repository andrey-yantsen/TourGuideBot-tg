from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tour_guide_bot import t
from tour_guide_bot.bot.admin.tour.pricing.add import AddPricingHandler
from tour_guide_bot.helpers.product_selector import SelectProductHandler
from tour_guide_bot.models.guide import Product, Tour


class EditPricingHandler(AddPricingHandler, SelectProductHandler):
    @classmethod
    def get_handlers(cls):
        return [
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        cls.partial(cls.send_tour_selector),
                        cls.get_callback_data_pattern(),
                    ),
                ],
                states={
                    cls.STATE_SELECT_TOUR: cls.get_select_tour_handlers(),
                    cls.STATE_LANGUAGE_SELECTION: cls.get_select_language_handlers(),
                    cls.STATE_SELECT_PRODUCT: cls.get_select_product_handlers(),
                    cls.STATE_WAITING_FOR_GUESTS_COUNT: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.save_guests_count),
                        ),
                    ],
                    cls.STATE_WAITING_FOR_CURRENCY: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.save_currency),
                        ),
                    ],
                    cls.STATE_WAITING_FOR_PRICE: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.save_price),
                        ),
                    ],
                    cls.STATE_WAITING_FOR_DURATION: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.save_duration),
                        ),
                    ],
                    cls.STATE_WAITING_FOR_TITLE: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.save_title),
                        ),
                    ],
                    cls.STATE_WAITING_FOR_DESCRIPTION: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.save_description),
                        ),
                    ],
                },
                fallbacks=[
                    CommandHandler("cancel", cls.partial(cls.cancel)),
                    CallbackQueryHandler(cls.partial(cls.cancel), "cancel"),
                    MessageHandler(filters.COMMAND, cls.partial(cls.unknown_command)),
                    MessageHandler(filters.ALL, cls.partial(cls.unexpected_message)),
                    # add editted message fallback
                ],
                name="admin-pricing-delete",
                persistent=True,
            )
        ]

    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-tour", "Update a product")

    def get_tour_selection_message(self, language: str) -> str:
        return t(language).pgettext(
            "admin-tours", "Please select the tour for updating a price."
        )

    async def get_product_selection_message(
        self,
        tour_id: int,
        language: str,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> str:
        return t(language).pgettext(
            "admin-tours", "Please select the product you want to update."
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
        context.user_data["product_id"] = product.id

        language = await self.get_language(update, context)

        msg = (
            t(language)
            .pgettext(
                "admin-tours",
                "Current price is {}.",
            )
            .format(await product.formatted_name(language))
        )

        msg += "\n\n" + t(language).pgettext(
            "admin-tours",
            "Current title:\n<code>{title}</code>\n\nCurrent description:\n<code>{description}</code>",
        ).format(title=product.title, description=product.description)

        msg += "\n\n" + t(language).pgettext(
            "admin-tours",
            "Please send me the number of guests (>= 1), or /cancel to abort.",
        )

        await self.edit_or_reply_text(
            update,
            context,
            msg,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

        return self.STATE_WAITING_FOR_GUESTS_COUNT

    async def save_product(
        self, tour: Tour, context: ContextTypes.DEFAULT_TYPE
    ) -> Product:
        old_product: Product = await self.db_session.scalar(
            select(Product).where(Product.id == context.user_data["product_id"])
        )
        old_product.available = False
        self.db_session.add(old_product)

        context.user_data["provider_id"] = old_product.payment_provider_id

        return await super().save_product(tour, context)

    @classmethod
    async def is_available(cls, db_session: AsyncSession) -> bool:
        products_count: int = await db_session.scalar(
            select(func.count(Product.id)).where(Product.available == True)  # noqa
        )
        return products_count > 0
