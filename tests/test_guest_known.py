from telethon.tl.custom.conversation import Conversation


async def test_bot_recognise_added_user(conversation: Conversation, app, guest):
    await conversation.send_message("/start")
    response = await conversation.get_response()
    assert (
        response.message == "welcome"
    ), "Unexpected first message from a configured bot"

    response = await conversation.get_response()
    assert (
        "Unfortunately, no tours are available for you at the moment"
        in response.message
    ), "Unexpected response to a user without tours"
