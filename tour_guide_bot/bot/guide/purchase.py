from datetime import datetime, timedelta
from itertools import groupby
from typing import Sequence

from babel.dates import format_datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from tour_guide_bot import t
from tour_guide_bot.helpers.currency import Currency
from tour_guide_bot.helpers.telegram import get_tour_description
from tour_guide_bot.helpers.tours_selector import SelectTourHandler
from tour_guide_bot.models.guide import (
    Invoice,
    Product,
    Subscription,
    Tour,
    TourTranslation,
)


class PurchaseCommandHandler(SelectTourHandler):
    @classmethod
    def get_handlers(cls):
        return [
            CommandHandler("purchase", cls.partial(cls.send_tour_selector)),
            CallbackQueryHandler(
                cls.partial(cls.purchase),
                cls.get_callback_data_pattern("purchase", r"(\d+)"),
            ),
            CallbackQueryHandler(
                cls.partial(cls.cancel),
                cls.get_callback_data_pattern("cancel_product_selection"),
            ),
            PreCheckoutQueryHandler(cls.partial(cls.pre_checkout)),
            MessageHandler(
                filters.SUCCESSFUL_PAYMENT, cls.partial(cls.successful_payment)
            ),
            *cls.get_select_tour_handlers(),
        ]

    async def successful_payment(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        user = await self.get_user(update, context)
        invoice_id = int(update.message.successful_payment.invoice_payload[2:])
        invoice: Invoice | None = await self.db_session.scalar(
            select(Invoice).where(Invoice.id == invoice_id)
        )

        subscription: Subscription = await self.db_session.scalar(
            select(Subscription).where(
                (Subscription.guest_id == user.guest_id)
                & (Subscription.tour_id == invoice.tour_id)
                & (Subscription.expire_ts >= datetime.now())
            )
        )

        if subscription:
            subscription.is_user_notified = True
            subscription.invoice_id = invoice_id
            subscription.expire_ts += timedelta(days=invoice.duration_days)
        else:
            subscription = Subscription(
                guest=user.guest,
                tour_id=invoice.tour_id,
                is_user_notified=True,
                expire_ts=datetime.now() + timedelta(days=invoice.duration_days),
                invoice_id=invoice_id,
            )

        invoice.subscription = subscription
        invoice.paid = True

        self.db_session.add(subscription)
        self.db_session.add(invoice)
        await self.db_session.commit()
        await update.message.reply_text(
            t(user.language)
            .pgettext(
                "guest-tour-purchase",
                "Thank you for the purchase! You can now access the tour by "
                "sending /tours and following the instructions. "
                "Access to the tour will expire at {} UTC.",
            )
            .format(format_datetime(subscription.expire_ts, locale=user.language))
        )

    async def pre_checkout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        language = await self.get_language(update, context)
        query = update.pre_checkout_query
        if not query.invoice_payload[0:2] == "i:":
            await query.answer(
                ok=False,
                error_message=t(language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )
            return

        invoice_id = int(query.invoice_payload[2:])
        invoice: Invoice | None = await self.db_session.scalar(
            select(Invoice).where(Invoice.id == invoice_id)
        )

        if not invoice or invoice.paid:
            await query.answer(
                ok=False,
                error_message=t(language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )
            return

        await query.answer(ok=True)

    async def purchase(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        product_id: int | None = None,
    ):
        language = await self.get_language(update, context)
        user = await self.get_user(update, context)
        product: Product | None = await self.db_session.scalar(
            select(Product)
            .options(
                selectinload(Product.tour)
                .selectinload(Tour.translations)
                .selectinload(TourTranslation.sections),
                selectinload(Product.payment_provider),
            )
            .where(
                Product.id
                == int(product_id if product_id else context.matches[0].group(1))
            )
        )

        if product is None:
            await update.callback_query.answer()
            await self.edit_or_reply_text(
                update,
                context,
                t(language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )

            return

        invoice = Invoice(
            product=product,
            tour=product.tour,
            guest=user.guest,
            payment_provider_id=product.payment_provider_id,
            currency=product.currency,
            price=product.price,
            duration_days=product.duration_days,
        )

        self.db_session.add(invoice)
        await self.db_session.commit()

        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.delete()

        await context.bot.send_invoice(
            update.effective_chat.id,
            title=product.title,
            description=product.description,
            payload="i:" + str(invoice.id),
            currency=invoice.currency,
            start_parameter="p" + str(invoice.product_id),
            provider_token=product.payment_provider.config["token"],
            prices=[
                {
                    "label": t(language)
                    .npgettext(
                        "guest-tour-purchase",
                        "{} day access",
                        "{} days access",
                        product.duration_days,
                    )
                    .format(product.duration_days),
                    "amount": invoice.price,
                }
            ],
            protect_content=True,
        )

    async def after_tour_selected(
        self,
        tour: Tour,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_tour: bool,
    ):
        language = await self.get_language(update, context)

        all_products = (
            await self.db_session.scalars(
                select(Product)
                .where((Product.tour_id == tour.id) & (Product.available == True))
                .order_by(Product.price)
            )
        ).all()

        products_per_language = {
            k: list(v) for k, v in groupby(all_products, lambda p: p.language)
        }

        if language in products_per_language:
            products = products_per_language[language]
        elif context.application.default_language in products_per_language:
            products = products_per_language[context.application.default_language]
        else:
            await self.edit_or_reply_text(
                update,
                context,
                t(language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )
            return

        keyboard = []

        for product in products:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=t(language)
                        .npgettext(
                            "guest-tour-purchase",
                            "{n}-day access for {price}",
                            "{n}-days access for {price}",
                            n=product.duration_days,
                        )
                        .format(
                            n=product.duration_days,
                            price=await Currency.price_from_telegram(
                                product.currency, product.price
                            ),
                        ),
                        callback_data=self.get_callback_data("purchase", product.id),
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

        msg = get_tour_description(tour, language, context)

        msg += "\n\n" + t(language).pgettext(
            "guest-tour-purchase",
            "Please select the access duration you want to purchase.",
        )

        await self.edit_or_reply_text(
            update, context, msg, reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def get_tour_selection_message(self, language: str) -> str:
        return t(language).pgettext(
            "guest-tour-purchase",
            "Please select the tour you want to purchase. You'll "
            "see the description of the tour after you select it.",
        )

    async def get_acceptable_tours(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> Sequence[Tour]:
        return (
            await self.db_session.scalars(
                select(Tour)
                .options(
                    selectinload(Tour.translations),
                )
                .where(Tour.products.any(available=True))
            )
        ).all()

    async def handle_no_tours_found(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)
        await self.edit_or_reply_text(
            update,
            context,
            t(language).pgettext(
                "guest-tour-purchase",
                "Unfortunately, there are no tours available for "
                "purchase online at the moment.",
            ),
        )
