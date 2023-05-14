from telethon.tl.custom.conversation import Conversation

from .conftest import get_phone_number_request


async def test_success_auth_flow(conversation: Conversation, app):
    await conversation.send_message("/start")
    response = await conversation.get_response()
    assert (
        response.message == "welcome"
    ), "Unexpected first message from a configured bot"

    response = await get_phone_number_request(conversation)
    await response.click(0, share_phone=True)

    response = await conversation.get_response()
    assert (
        "Unfortunately, no tours are available for you at the moment"
        in response.message
    ), "Unexpected response to a user without tours"
