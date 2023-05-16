from telethon.events import MessageEdited
from telethon.tl.custom import Message
from telethon.tl.custom.conversation import Conversation
from telethon.tl.types.messages import BotCallbackAnswer


async def test_change_welcome_message(admin_conversation: Conversation, app):
    conversation = admin_conversation
    await conversation.send_message("/configure")
    response: Message = await conversation.get_response()

    assert (
        "Please select the parameter you want to change" in response.message
    ), "Unexpected message in response to /configure"

    response = await response.click(text="Guide welcome message")
    assert isinstance(
        response, BotCallbackAnswer
    ), "BotCallbackAnswer didn't arrive after the inline button click"

    event: MessageEdited.Event = await conversation.wait_event(MessageEdited())
    msg: Message = event.message

    response = await msg.click(text="English")
    assert isinstance(
        response, BotCallbackAnswer
    ), "BotCallbackAnswer didn't arrive after the inline button click"

    event: MessageEdited.Event = await conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert (
        "The bot currently has the following welcome message" in msg.message
    ), "Unexpected message after selecting the language"

    current_welcome_message: Message = await conversation.get_response()

    assert (
        current_welcome_message.message == "welcome"
    ), "Unexpected old welcome message"

    await conversation.send_message("new welcome message")
    response = await conversation.get_response()

    assert (
        "welcome message has been changed" in response.message
    ), "Unexpected response to welcome message update"

    await conversation.send_message("/guest")
    response = await conversation.get_response()

    assert (
        "in guest mode now" in response.message
    ), "Unexpected message in response to the guest mode switch"

    await conversation.send_message("/start")
    response = await conversation.get_response()

    assert response.message == "new welcome message", "Unexpected new welcome message"
