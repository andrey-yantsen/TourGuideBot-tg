from telethon.tl.custom import Message
from telethon.tl.custom.conversation import Conversation

from .conftest import get_phone_number_request


async def test_success_auth_flow_configured_app(
    conversation: Conversation, app, bot_token
):
    await conversation.send_message("/admin")
    response: Message = await get_phone_number_request(conversation)
    await response.click(0, share_phone=True)

    response: Message = await conversation.get_response()
    assert (
        "Please send me the token to confirm ownership" in response.message
    ), "Unexpected response to an unknown phone number"

    await conversation.send_message(bot_token)

    response: Message = await conversation.get_response()

    assert (
        "Admin permissions confirmed" in response.message
    ), "Unexpected message in response to the secret phrase"


async def test_success_auth_flow_unconfigured_app(
    conversation: Conversation, unconfigured_app, bot_token
):
    await conversation.send_message("/admin")
    response: Message = await get_phone_number_request(conversation)
    await response.click(0, share_phone=True)

    response: Message = await conversation.get_response()
    assert (
        "Please send me the token to confirm ownership" in response.message
    ), "Unexpected response to an unknown phone number"

    await conversation.send_message(bot_token)

    response: Message = await conversation.get_response()

    assert (
        "Admin permissions confirmed" in response.message
    ), "Unexpected message in response to the secret phrase"
