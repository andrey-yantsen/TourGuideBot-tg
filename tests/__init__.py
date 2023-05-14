from telethon.tl.custom.conversation import Conversation
from telethon.tl.types import KeyboardButtonRequestPhone


async def get_phone_number_request(conversation: Conversation):
    response = await conversation.get_response()
    assert response.reply_markup is not None, "No reply markup"
    assert response.reply_markup.rows, "No reply markup rows"
    assert response.reply_markup.rows[0].buttons, "No reply markup buttons"
    assert isinstance(
        response.reply_markup.rows[0].buttons[0], KeyboardButtonRequestPhone
    ), "No request phone button"
    return response
