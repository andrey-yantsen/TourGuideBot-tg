from asyncio import sleep

from telethon.tl.custom import Message
from telethon.tl.custom.conversation import Conversation


async def test_switching_mode_multiple_times(
    conversation: Conversation, app, admin, guest
):
    await conversation.send_message("/admin")
    response: Message = await conversation.get_response()

    assert (
        "Welcome to the admin mode" in response.message
    ), "Unexpected message in response to the admin mode switch"

    await sleep(0.2)
    await conversation.send_message("/guest")
    response: Message = await conversation.get_response()

    assert (
        "in guest mode now" in response.message
    ), "Unexpected message in response to the guest mode switch"

    await sleep(0.2)
    await conversation.send_message("/admin")
    response: Message = await conversation.get_response()

    assert (
        "Welcome to the admin mode" in response.message
    ), "Unexpected message in response to the admin mode switch"

    await sleep(0.2)
    await conversation.send_message("/guest")
    response: Message = await conversation.get_response()

    assert (
        "in guest mode now" in response.message
    ), "Unexpected message in response to the guest mode switch"
