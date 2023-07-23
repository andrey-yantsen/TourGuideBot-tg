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
from tour_guide_bot.helpers.payment_provider_selector import PaymentProviderSelector
from tour_guide_bot.helpers.telegram import SubcommandHandler, get_tour_title
from tour_guide_bot.helpers.tours_selector import SelectTourHandler
from tour_guide_bot.models.guide import Product, Tour
from tour_guide_bot.models.settings import PaymentProvider


class AddPricingHandler(
    SubcommandHandler, SelectTourHandler, SelectLanguageHandler, PaymentProviderSelector
):
    STATE_WAITING_FOR_GUESTS_COUNT: ClassVar[int] = 1
    STATE_WAITING_FOR_CURRENCY: ClassVar[int] = 2
    STATE_WAITING_FOR_PRICE: ClassVar[int] = 3
    STATE_WAITING_FOR_DURATION: ClassVar[int] = 4
    STATE_WAITING_FOR_TITLE: ClassVar[int] = 5
    STATE_WAITING_FOR_DESCRIPTION: ClassVar[int] = 6

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
                    cls.STATE_SELECT_PAYMENT_PROVIDER: cls.get_select_payment_provider_handlers(),
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
                name="admin-pricing-add",
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
            "admin-tours", "Please select the tour for adding a new price."
        )

    def get_language_selection_message(self, user_language: str) -> str:
        return t(user_language).pgettext(
            "admin-tours",
            "Please select the language you want to update. "
            "Keep in mind that you have to set the price for each "
            "language the tour has in order to everything work properly.",
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
        return await self.send_payment_provider_selector(update, context)

    async def after_payment_provider_selected(
        self,
        provider: PaymentProvider,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_provider: bool,
    ):
        context.user_data["provider_id"] = provider.id

        language = await self.get_language(update, context)

        await update.callback_query.answer()

        await self.edit_or_reply_text(
            update,
            context,
            t(language).pgettext(
                "admin-tours",
                "Please send me the number of guests (>= 1), or /cancel to abort.",
            ),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

        return self.STATE_WAITING_FOR_GUESTS_COUNT

    def get_payment_provider_selection_message(self, language: str) -> str:
        return t(language).pgettext(
            "admin-tours", "Please select the payment provider you want to use."
        )

    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-tour", "Add a new product")

    @classmethod
    async def is_available(cls, db_session: AsyncSession) -> bool:
        tours_count: int = await db_session.scalar(select(func.count(Tour.id)))
        payment_provider: int = await db_session.scalar(
            select(func.count(PaymentProvider.id)).where(
                PaymentProvider.enabled == True  # noqa
            )
        )
        return tours_count > 0 and payment_provider > 0

    async def save_guests_count(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)
        guests_count = update.message.text.strip()

        if not guests_count.isdigit() or int(guests_count) < 1:
            await update.message.reply_text(
                t(language).pgettext(
                    "admin-tours",
                    "Please enter a number greater than 0.",
                )
            )
            return None

        context.user_data["guests_count"] = int(guests_count)

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

        context.user_data["duration"] = duration

        await update.message.reply_text(
            t(language).pgettext(
                "admin-tours",
                "Please send me the title to display with the purchase "
                "(max 32 chars; no formatting), or /cancel to abort.",
            )
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

    async def save_product(
        self, tour: Tour, context: ContextTypes.DEFAULT_TYPE
    ) -> Product:
        currency = context.user_data["currency"]
        price = context.user_data["price"]
        duration = context.user_data["duration"]
        guests_count = context.user_data["guests_count"]
        provider_id = context.user_data["provider_id"]
        description = context.user_data["description"]

        product = Product(
            tour=tour,
            currency=currency,
            price=price,
            duration_days=duration,
            payment_provider_id=provider_id,
            language=context.user_data["language"],
            title=context.user_data["title"],
            description=description,
            guests=guests_count,
        )

        self.db_session.add(product)

        return product

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

        currency = context.user_data["currency"]
        price = context.user_data["price"]

        tour: Tour | None = await self.db_session.scalar(
            select(Tour)
            .where(Tour.id == context.user_data["tour_id"])
            .options(selectinload(Tour.translations))
        )

        product = await self.save_product(tour, context)
        await self.db_session.commit()

        await update.message.reply_text(
            t(language)
            .npgettext(
                "admin-tours",
                "From now on users can buy {}-day access to {} for {} ({}).",
                "From now on users can buy {}-days access to {} for {} ({}).",
                product.duration_days,
            )
            .format(
                product.duration_days,
                get_tour_title(tour, language, context),
                await Currency.price_from_telegram(currency, price),
                t(language)
                .npgettext(
                    "admin-tours",
                    "for {} guest",
                    "for {} guests",
                    product.guests,
                )
                .format(product.guests),
            )
        )

        return ConversationHandler.END
