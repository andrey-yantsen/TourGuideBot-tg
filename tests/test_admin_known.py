from telethon.tl.custom.conversation import Conversation


async def test_bot_recognise_added_user(conversation: Conversation, app, admin):
    await conversation.send_message("/admin")
    response = await conversation.get_response()

    assert (
        "Welcome to the admin mode" in response.message
    ), "Unexpected message in response to the admin mode switch"
