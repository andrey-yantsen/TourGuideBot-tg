import json
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from telethon import TelegramClient
from telethon.tl import types
from telethon.tl.custom import Message
from telethon.tl.custom.conversation import Conversation
from telethon.tl.functions.payments import GetPaymentFormRequest, SendPaymentFormRequest

from tour_guide_bot.models.guide import Guest, Subscription


@pytest.mark.usefixtures("app", "tours", "payment_provider")
async def test_success_payment(
    conversation: Conversation,
    telegram_client: TelegramClient,
    db_engine: AsyncEngine,
    guest: Guest,
):
    await conversation.send_message("/purchase")
    # Skip message about having only one tour
    await conversation.get_response()

    # Invoice
    response: Message = await conversation.get_response()
    assert isinstance(response.media, types.MessageMediaInvoice)

    invoice = types.InputInvoiceMessage(response.input_chat, response.id)
    form: types.payments.PaymentForm = await telegram_client(
        GetPaymentFormRequest(invoice)
    )

    assert (
        form.native_provider == "stripe"
    ), "Only stripe is supported in the test for now"

    # https://stripe.com/docs/testing?testing-method=tokens#cards
    payload = {"type": "token", "id": "tok_visa"}

    now = datetime.now()
    _purchase: types.payments.PaymentForm = await telegram_client(
        SendPaymentFormRequest(
            form.form_id,
            invoice,
            types.InputPaymentCredentials(types.DataJSON(json.dumps(payload))),
        )
    )

    response: Message = await conversation.get_response()

    assert (
        "You can now access the tour" in response.message
    ), "Unexpected response to a successful payment"

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        stmt = select(Subscription).where(Subscription.guest == guest)
        s: Subscription | None = await session.scalar(stmt)

        assert (s.expire_ts - now).days == 1, "Unexpected subscription duration"
