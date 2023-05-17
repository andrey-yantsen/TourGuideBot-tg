import pytest
from telegram.ext import CallbackContext
from telethon.tl.custom import Message
from telethon.tl.custom.conversation import Conversation

from tour_guide_bot.bot.app import Application
from tour_guide_bot.models.guide import MessageType


@pytest.mark.approved_tour_ids(1)
@pytest.mark.usefixtures("guest", "approved_tours")
async def test_single_tour(
    conversation: Conversation, tours_as_dicts: list[dict], app: Application
):
    ctx = CallbackContext(app)
    await conversation.send_message("x")
    await app.check_new_approved_tours(ctx)
    response: Message = await conversation.get_response()
    assert (
        'You have a new tour available — "%s"' % tours_as_dicts[0]["en"]["title"]
        in response.message
    )


@pytest.mark.approved_tour_ids(1, 2)
@pytest.mark.tours(
    {
        "en": {
            "title": "Test tour 1",
            "sections": [
                {
                    "title": "Test section 1.1",
                    "content": [
                        {
                            "type": MessageType.text,
                            "content": {"text": r"Test text 1\.1\.1"},
                        },
                    ],
                },
                {
                    "title": "Test section 1.2",
                    "content": [
                        {
                            "type": MessageType.text,
                            "content": {"text": r"Test text 1\.2\.1"},
                        },
                    ],
                },
            ],
        }
    },
    {
        "en": {
            "title": "Test tour 2",
            "sections": [
                {
                    "title": "Test section 2.1",
                    "content": [
                        {
                            "type": MessageType.text,
                            "content": {"text": r"Test text 2\.1\.1"},
                        },
                    ],
                },
                {
                    "title": "Test section 2.2",
                    "content": [
                        {
                            "type": MessageType.text,
                            "content": {"text": r"Test text 2\.2\.1"},
                        },
                    ],
                },
            ],
        }
    },
)
@pytest.mark.usefixtures("guest", "approved_tours")
async def test_multiple_tours(
    conversation: Conversation, tours_as_dicts: list[dict], app: Application
):
    ctx = CallbackContext(app)
    await conversation.send_message("x")
    await app.check_new_approved_tours(ctx)

    tours_titles = [tour["en"]["title"] for tour in tours_as_dicts]

    response: Message = await conversation.get_response()
    expected_msg = 'You have a new tour available — "%s".' % tours_titles[0]

    if expected_msg not in response.message:
        tours_titles.reverse()
        expected_msg = 'You have a new tour available — "%s".' % tours_titles[0]

    tours_titles.pop(0)

    assert expected_msg in response.message

    response: Message = await conversation.get_response()
    expected_msg = 'You have a new tour available — "%s".' % tours_titles[0]
    assert expected_msg in response.message


@pytest.mark.approved_tour_ids(2)
@pytest.mark.tours(
    {
        "en": {
            "title": "Test tour 1",
            "sections": [
                {
                    "title": "Test section 1.1",
                    "content": [
                        {
                            "type": MessageType.text,
                            "content": {"text": r"Test text 1\.1\.1"},
                        },
                    ],
                },
                {
                    "title": "Test section 1.2",
                    "content": [
                        {
                            "type": MessageType.text,
                            "content": {"text": r"Test text 1\.2\.1"},
                        },
                    ],
                },
            ],
        }
    },
    {
        "en": {
            "title": "Test tour 2",
            "sections": [
                {
                    "title": "Test section 2.1",
                    "content": [
                        {
                            "type": MessageType.text,
                            "content": {"text": r"Test text 2\.1\.1"},
                        },
                    ],
                },
                {
                    "title": "Test section 2.2",
                    "content": [
                        {
                            "type": MessageType.text,
                            "content": {"text": r"Test text 2\.2\.1"},
                        },
                    ],
                },
            ],
        }
    },
)
@pytest.mark.usefixtures("guest", "approved_tours")
async def test_multiple_tours_single_approved(
    conversation: Conversation, tours_as_dicts: list[dict], app: Application
):
    ctx = CallbackContext(app)
    await conversation.send_message("x")
    await app.check_new_approved_tours(ctx)
    response: Message = await conversation.get_response()

    assert (
        'You have a new tour available — "%s"' % tours_as_dicts[1]["en"]["title"]
        in response.message
    )

    try:
        response: Message = await conversation.get_response(timeout=5)
        assert False, "Unexpected message received"
    except TimeoutError:
        pass
