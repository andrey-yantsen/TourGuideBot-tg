from asyncio import sleep

import pytest
from telethon.tl.custom import Message
from telethon.tl.custom.conversation import Conversation

from .conftest import get_phone_number_request


@pytest.mark.usefixtures("app")
async def test_success_auth_flow(conversation: Conversation):
    await conversation.send_message("/start")
    response: Message = await conversation.get_response()
    assert (
        response.message == "welcome"
    ), "Unexpected first message from a configured bot"

    response: Message = await get_phone_number_request(conversation)
    await response.click(0, share_phone=True)
    await sleep(0.2)

    response: Message = await conversation.get_response()
    assert (
        "Unfortunately, no tours are available for you at the moment"
        in response.message
    ), "Unexpected response to a user without tours"


@pytest.mark.usefixtures("app")
async def test_accepts_only_current_contact(conversation: Conversation):
    await conversation.send_message("/start")
    response: Message = await conversation.get_response()
    assert (
        response.message == "welcome"
    ), "Unexpected first message from a configured bot"

    response: Message = await get_phone_number_request(conversation)
    await response.click(0, share_phone="+99999999999")
    await sleep(0.2)

    response: Message = await conversation.get_response()
    assert (
        "Please send me your contact number and not somebody else's" in response.message
    ), "Unexpected response to sending a random contact"
