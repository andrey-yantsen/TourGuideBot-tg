from datetime import datetime, timedelta
from typing import Sequence

from babel.dates import format_datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from tour_guide_bot import t
from tour_guide_bot.helpers.product_selector import SelectProductHandler
from tour_guide_bot.helpers.telegram import get_tour_description
from tour_guide_bot.helpers.tours_selector import SelectTourHandler
from tour_guide_bot.models.guide import (
    Invoice,
    Product,
    Subscription,
    Tour,
    TourTranslation,
)


class PurchaseCommandHandler(SelectTourHandler, SelectProductHandler):
    @classmethod
    def get_handlers(cls):
        return [
            CommandHandler("purchase", cls.partial(cls.send_tour_selector)),
            PreCheckoutQueryHandler(cls.partial(cls.pre_checkout)),
            MessageHandler(
                filters.SUCCESSFUL_PAYMENT, cls.partial(cls.successful_payment)
            ),
            *cls.get_select_tour_handlers(),
            *cls.get_select_product_handlers(),
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

    async def after_product_selected(
        self,
        product: Product,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_product: bool,
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
            .where(Product.id == product.id)
        )

        invoice = Invoice(
            product=product,
            tour=product.tour,
            guest=user.guest,
            payment_provider_id=product.payment_provider_id,
            currency=product.currency,
            price=product.price,
            duration_days=product.duration_days,
            guests=product.guests,
        )

        self.db_session.add(invoice)
        await self.db_session.commit()

        if update.callback_query:
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

        return await self.send_product_selector(tour.id, language, update, context)

    def get_tour_selection_message(self, language: str) -> str:
        return t(language).pgettext(
            "guest-tour-purchase",
            "Please select the tour you want to purchase. You'll "
            "see the description of the tour after you select it.",
        )

    async def get_product_selection_message(
        self,
        tour_id: int,
        language: str,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> str:
        tour: Tour = await self.db_session.scalar(
            select(Tour)
            .options(selectinload(Tour.translations))
            .where(Tour.id == tour_id)
        )
        msg = get_tour_description(tour, language, context)

        msg += "\n\n" + t(language).pgettext(
            "guest-tour-purchase",
            "Please select the product you want to purchase.",
        )

        return msg

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
