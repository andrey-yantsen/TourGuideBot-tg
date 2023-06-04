from datetime import datetime, timedelta
from typing import Sequence

from babel.dates import format_datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import BaseHandlerCallback
from tour_guide_bot.models.guide import (
    Invoice,
    Product,
    Subscription,
    Tour,
    TourTranslation,
)


class PurchaseCommandHandler(BaseHandlerCallback):
    @classmethod
    def get_handlers(cls):
        return [
            CommandHandler("purchase", cls.partial(cls.start)),
            CallbackQueryHandler(cls.partial(cls.purchase), r"^purchase:(\d+)$"),
            PreCheckoutQueryHandler(cls.partial(cls.pre_checkout)),
            MessageHandler(
                filters.SUCCESSFUL_PAYMENT, cls.partial(cls.successful_payment)
            ),
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
            subscription.expire_ts += timedelta(days=invoice.duration_days)
        else:
            subscription = Subscription(
                guest=user.guest,
                tour_id=invoice.tour_id,
                is_user_notified=True,
                expire_ts=datetime.now() + timedelta(days=invoice.duration_days),
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
        query = update.pre_checkout_query
        if not query.invoice_payload[0:2] == "i:":
            return

        invoice_id = int(query.invoice_payload[2:])
        invoice: Invoice | None = await self.db_session.scalar(
            select(Invoice).where(Invoice.id == invoice_id)
        )

        language = await self.get_language(update, context)

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

    async def single_tour_purchase(
        self,
        tour: Tour,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_short_path: bool = False,
    ):
        language = await self.get_language(update, context)

        available_products = [product for product in tour.products if product.available]

        if len(available_products) == 0:
            raise NotImplementedError()

        if len(available_products) == 1:
            if is_short_path:
                await self.edit_or_reply_text(
                    update,
                    context,
                    t(language).pgettext(
                        "guest-tour-purchase",
                        "Only one tour available for purchasing online at the moment.",
                    ),
                )

            await self.purchase(update, context, available_products[0].id)

            return

        raise NotImplementedError()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        tours_with_products: Sequence[Tour] = (
            await self.db_session.scalars(
                select(Tour)
                .options(
                    selectinload(Tour.products),
                    selectinload(Tour.translations).selectinload(
                        TourTranslation.sections
                    ),
                )
                .where(Tour.products.any(available=True))
            )
        ).all()

        if len(tours_with_products) == 0:
            raise NotImplementedError()

        if len(tours_with_products) == 1:
            await self.single_tour_purchase(
                tours_with_products[0], update, context, True
            )
            return

        raise NotImplementedError()
