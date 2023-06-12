import json
from datetime import datetime

import aiohttp
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from telethon import TelegramClient
from telethon.tl import types
from telethon.tl.custom import Message
from telethon.tl.custom.conversation import Conversation
from telethon.tl.functions.payments import GetPaymentFormRequest, SendPaymentFormRequest

from tour_guide_bot.models.guide import Guest, Subscription


async def get_payment_token(
    form: types.payments.PaymentForm, token_request_data: dict = {}
) -> dict:
    assert (
        form.native_provider == "stripe"
    ), "Only stripe is supported in the test for now"

    native_params = json.loads(form.native_params.data)

    default_token_request_data = {
        "card[number]": "4242424242424242",
        "card[exp_month]": "12",
        "card[exp_year]": "2030",
        "card[cvc]": "123",
        "card[name]": "Test User",
        "card[address_country]": "US",
        "card[address_zip]": "12345",
    }

    token_request_data = {**default_token_request_data, **token_request_data}

    async with aiohttp.ClientSession(
        auth=aiohttp.BasicAuth(login=native_params["publishable_key"])
    ) as session:
        async with session.post(
            "https://api.stripe.com/v1/tokens",
            data=aiohttp.FormData(token_request_data),
        ) as resp:
            assert resp.status == 200, "Failed to get a token"
            token = await resp.json()

    return {"type": token["type"], "id": token["id"]}


@pytest.mark.usefixtures("app", "tours", "payment_provider")
async def test_success_payment(
    conversation: Conversation,
    telegram_client: TelegramClient,
    db_engine: AsyncEngine,
    guest: Guest,
    tours_as_dicts: list[dict],
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

    token = await get_payment_token(form)

    now = datetime.now()
    _purchase: types.payments.PaymentForm = await telegram_client(
        SendPaymentFormRequest(
            form.form_id,
            invoice,
            types.InputPaymentCredentials(types.DataJSON(json.dumps(token))),
        )
    )

    response: Message = await conversation.get_response()

    assert (
        "You can now access the tour" in response.message
    ), "Unexpected response to a successful payment"

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        stmt = select(Subscription).where(Subscription.guest == guest)
        s: Subscription | None = await session.scalar(stmt)

        assert (s.expire_ts - now).days == tours_as_dicts[0]["products"][0][
            "duration_days"
        ], "Unexpected subscription duration"
