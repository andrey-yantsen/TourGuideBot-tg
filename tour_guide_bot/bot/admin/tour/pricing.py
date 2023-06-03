from typing import ClassVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
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
from tour_guide_bot.bot.admin.tour.helpers import SelectTourHandler
from tour_guide_bot.helpers.currency import Currency
from tour_guide_bot.helpers.telegram import SubcommandHandler, get_tour_title
from tour_guide_bot.models.guide import Product, Tour
from tour_guide_bot.models.settings import PaymentProvider


class PricingHandler(SubcommandHandler, SelectTourHandler):
    SKIP_TOUR_SELECTION_IF_SINGLE = False

    STATE_WAITING_FOR_CURRENCY: ClassVar[int] = 1
    STATE_WAITING_FOR_PRICE: ClassVar[int] = 2
    STATE_WAITING_FOR_DURATION: ClassVar[int] = 3

    @classmethod
    def get_handlers(cls):
        return [
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        cls.partial(cls.send_tour_selector), cls.get_callback_data()
                    ),
                ],
                states={
                    cls.STATE_WAITING_FOR_CURRENCY: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.save_new_currency),
                        ),
                    ],
                    cls.STATE_WAITING_FOR_PRICE: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.save_new_price),
                        ),
                    ],
                    cls.STATE_WAITING_FOR_DURATION: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.save_new_duration),
                        ),
                    ],
                    **cls.get_select_tour_handlers(),
                },
                fallbacks=[
                    CommandHandler("cancel", cls.partial(cls.cancel)),
                    CallbackQueryHandler(cls.partial(cls.cancel), "cancel"),
                    MessageHandler(filters.COMMAND, cls.partial(cls.unknown_command)),
                    # add editted message fallback
                ],
                name="admin-pricing-tour",
                persistent=True,
            )
        ]

    @staticmethod
    def cleanup_context(context: ContextTypes.DEFAULT_TYPE):
        for key in ("tour_id", "currency", "price"):
            if key in context.user_data:
                del context.user_data[key]

    def get_tour_selection_message(self, language: str) -> str:
        return t(language).pgettext(
            "admin-tours", "Please select the tour for updating the price."
        )

    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-tour", "Set/change a tour's price")

    @classmethod
    async def is_available(cls, db_session: AsyncSession) -> bool:
        tours_count: int = await db_session.scalar(select(func.count(Tour.id)))
        payment_provider: int = await db_session.scalar(
            select(func.count(PaymentProvider.id)).where(
                PaymentProvider.enabled is True
            )
        )
        return tours_count > 0 and payment_provider > 0

    async def after_tour_selected(
        self,
        tour: Tour,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_tour: bool,
    ):
        context.user_data["tour_id"] = tour.id
        language = await self.get_language(update, context)

        tour: Tour | None = await self.db_session.scalar(
            select(Tour)
            .where(Tour.id == tour.id)
            .options(selectinload(Tour.translations), selectinload(Tour.products))
        )

        available_products = [product for product in tour.products if product.available]

        await update.callback_query.answer()
        if available_products:
            product = available_products[0]
            msg = (
                t(language)
                .npgettext(
                    "admin-tours",
                    r"Current price is {} for {} day\.",
                    r"Current price is {} for {} days\.",
                    product.duration_days,
                )
                .format(
                    await Currency.price_from_telegram(product.currency, product.price),
                    product.duration_days,
                )
            )

            msg += " " + t(language).pgettext(
                "admin-tours",
                r"Please send me the currency for the new price, or /cancel to abort\.",
            )
        else:
            msg = t(language).pgettext(
                "admin-tours",
                r"Please send me the currency in which you want to charge your users, or /cancel to abort\.",
            )

        msg += "\n\n" + t(language).pgettext(
            "admin-tours",
            r"You can find more details about available currencies [here]("
            r"https://core.telegram.org/bots/payments#supported-currencies)\.",
        )

        await self.edit_or_reply_text(
            update,
            context,
            msg,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True,
        )
        return self.STATE_WAITING_FOR_CURRENCY

    async def save_new_currency(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)
        currency = update.message.text.strip().upper()

        if not await Currency.is_known_currency(currency):
            await update.message.reply_text(
                t(language).pgettext(
                    "admin-tours",
                    "Unknown currency provided. Please try again.",
                )
            )
            return None

        context.user_data["currency"] = currency

        await update.message.reply_text(
            t(language)
            .pgettext(
                "admin-tours",
                "Please send me the price of the tour in {}.",
            )
            .format(currency)
        )

        return self.STATE_WAITING_FOR_PRICE

    async def save_new_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        language = await self.get_language(update, context)
        price = update.message.text.strip()

        currency = context.user_data["currency"]

        try:
            price = await Currency.price_to_telegram(currency, price)
        except ValueError:
            price = None

        if not price or not await Currency.is_valid(currency, price):
            await update.message.reply_text(
                t(language).pgettext(
                    "admin-tours",
                    "Invalid value provided, please try again.",
                )
            )
            return None

        context.user_data["price"] = price

        await update.message.reply_text(
            t(language)
            .pgettext(
                "admin-tours",
                "How long (in days) {} should buy?",
            )
            .format(await Currency.price_from_telegram(currency, price))
        )

        return self.STATE_WAITING_FOR_DURATION

    async def save_new_duration(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)
        duration = update.message.text.strip()

        try:
            duration = int(duration)
        except ValueError:
            duration = None

        if not duration:
            await update.message.reply_text(
                t(language).pgettext(
                    "admin-tours",
                    "Invalid value provided, please try again.",
                )
            )
            self.cleanup_context(context)
            return None

        currency = context.user_data["currency"]
        price = context.user_data["price"]

        tour: Tour | None = await self.db_session.scalar(
            select(Tour)
            .where(Tour.id == context.user_data["tour_id"])
            .options(selectinload(Tour.translations))
        )

        product: Product | None = await self.db_session.scalar(
            select(Product).where((Product.tour == tour) & (Product.available is True))
        )

        if product:
            product.available = False
            self.db_session.add(product)

        payment_provider: PaymentProvider | None = await self.db_session.scalar(
            select(PaymentProvider).where(PaymentProvider.enabled is True)
        )

        if not payment_provider:
            await self.edit_or_reply_text(
                update,
                context,
                t(language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )
            self.cleanup_context(context)
            return ConversationHandler.END

        product = Product(
            tour=tour,
            currency=currency,
            price=price,
            duration_days=duration,
            payment_provider=payment_provider,
        )

        self.db_session.add(product)
        await self.db_session.commit()

        await update.message.reply_text(
            t(language)
            .npgettext(
                "admin-tours",
                "From now on users can buy {}-day access to {} for {}.",
                "From now on users can buy {}-days access to {} for {}.",
                product.duration_days,
            )
            .format(
                product.duration_days,
                get_tour_title(tour, language, context),
                await Currency.price_from_telegram(currency, price),
            )
        )

        return ConversationHandler.END
