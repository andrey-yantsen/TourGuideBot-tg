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
from tour_guide_bot.helpers.currency import Currency
from tour_guide_bot.helpers.language_selector import SelectLanguageHandler
from tour_guide_bot.helpers.telegram import SubcommandHandler, get_tour_title
from tour_guide_bot.helpers.tours_selector import SelectTourHandler
from tour_guide_bot.models.guide import Product, Tour
from tour_guide_bot.models.settings import PaymentProvider


class PricingHandler(SubcommandHandler, SelectTourHandler, SelectLanguageHandler):
    SKIP_LANGUAGE_SELECTION_IF_SINGLE = False

    STATE_WAITING_FOR_TITLE: ClassVar[int] = 1
    STATE_WAITING_FOR_DESCRIPTION: ClassVar[int] = 2
    STATE_WAITING_FOR_CURRENCY: ClassVar[int] = 3
    STATE_WAITING_FOR_PRICE: ClassVar[int] = 4
    STATE_WAITING_FOR_DURATION: ClassVar[int] = 5

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
                    cls.STATE_SELECT_TOUR: cls.get_select_tour_handlers(),
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
                    cls.STATE_LANGUAGE_SELECTION: cls.get_select_language_handlers(),
                },
                fallbacks=[
                    CommandHandler("cancel", cls.partial(cls.cancel)),
                    CallbackQueryHandler(cls.partial(cls.cancel), "cancel"),
                    MessageHandler(filters.COMMAND, cls.partial(cls.unknown_command)),
                    MessageHandler(filters.ALL, cls.partial(cls.unexpected_message)),
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

    def get_language_selection_message(self, user_language: str) -> str:
        return t(user_language).pgettext(
            "admin-tours",
            "Please select the language you want to update. "
            "Keep in mind that you have to set the price for each "
            "language the tour has in order to everything work properly.",
        )

    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-tour", "Set/change a tour's price")

    @classmethod
    async def is_available(cls, db_session: AsyncSession) -> bool:
        tours_count: int = await db_session.scalar(select(func.count(Tour.id)))
        payment_provider: int = await db_session.scalar(
            select(func.count(PaymentProvider.id)).where(
                PaymentProvider.enabled == True  # noqa
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

        return await self.send_language_selector(update, context)

    async def after_language_selected(
        self,
        language: str,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_language: bool,
    ):
        context.user_data["language"] = language

        language = await self.get_language(update, context)

        tour: Tour | None = await self.db_session.scalar(
            select(Tour)
            .where(Tour.id == context.user_data["tour_id"])
            .options(selectinload(Tour.translations), selectinload(Tour.products))
        )

        available_products = [
            product
            for product in tour.products
            if product.available and product.language == context.user_data["language"]
        ]

        await update.callback_query.answer()
        msg = ""
        if available_products:
            product = available_products[0]
            msg = (
                t(language)
                .npgettext(
                    "admin-tours",
                    "Current price is {} for {} day.",
                    "Current price is {} for {} days.",
                    product.duration_days,
                )
                .format(
                    await Currency.price_from_telegram(product.currency, product.price),
                    product.duration_days,
                )
            )

            msg += "\n\n" + t(language).pgettext(
                "admin-tours",
                "Current title:\n<code>{0}</code>\n\nCurrent description:\n<code>{1}</code>",
            ).format(product.title, product.description)

            msg += "\n\n"

        msg += t(language).pgettext(
            "admin-tours",
            "Please send me the title to display with the purchase "
            "(max 32 chars; no formatting), or /cancel to abort.",
        )

        await self.edit_or_reply_text(
            update,
            context,
            msg,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return self.STATE_WAITING_FOR_TITLE

    async def save_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        language = await self.get_language(update, context)
        title = update.message.text.strip()

        if len(title) > 32:
            await update.message.reply_text(
                t(language)
                .pgettext(
                    "admin-tours",
                    "Title is too long. You sent {len} characters, "
                    "but it should be 32 max. Please try again.",
                )
                .format(len=len(title))
            )
            return None

        context.user_data["title"] = title

        await update.message.reply_text(
            t(language).pgettext(
                "admin-tours",
                "Please send me the description of the tour to be "
                "displayed in an invoice (255 chars max; no formatting).",
            )
        )

        return self.STATE_WAITING_FOR_DESCRIPTION

    async def save_description(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)
        description = update.message.text.strip()

        if len(description) > 255:
            await update.message.reply_text(
                t(language)
                .pgettext(
                    "admin-tours",
                    "Description is too long. You sent {len} characters, "
                    "but it should be 255 max. Please try again.",
                )
                .format(len=len(description))
            )
            return None

        context.user_data["description"] = description

        msg = t(language).pgettext(
            "admin-tours",
            "Please send me the currency in which you want to charge your users, or /cancel to abort.",
        )

        msg += "\n\n" + t(language).pgettext(
            "admin-tours",
            "You can find more details about available currencies "
            "<a href='https://core.telegram.org/bots/payments#supported-currencies'>here</a>"
            ".",
        )

        await update.message.reply_text(
            msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )

        return self.STATE_WAITING_FOR_CURRENCY

    async def save_currency(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    async def save_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    async def save_duration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            select(Product).where(
                (Product.tour == tour)
                & (Product.available == True)
                & (Product.language == context.user_data["language"])
            )
        )

        if product:
            product.available = False
            self.db_session.add(product)

        payment_provider: PaymentProvider | None = await self.db_session.scalar(
            select(PaymentProvider).where(PaymentProvider.enabled == True)
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
            language=context.user_data["language"],
            title=context.user_data["title"],
            description=context.user_data["description"],
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
