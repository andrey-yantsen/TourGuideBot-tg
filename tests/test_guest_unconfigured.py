from telethon.tl.custom.conversation import Conversation


async def test_start_to_unconfigured_bot(
    conversation: Conversation, unconfigured_app, bot_token
):
    await conversation.send_message("/start")
    response = await conversation.get_response()
    assert (
        "The bot is not configured yet" in response.message
    ), "Unexpected response from an unconfigured bot"
