import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import selectinload
from telethon.events import MessageEdited
from telethon.tl.custom import Message
from telethon.tl.custom.conversation import Conversation

from tour_guide_bot.models.guide import (
    Tour,
    TourSection,
    TourTranslation,
)


async def add_tour(conversation: Conversation, prefix: str = ""):
    event: MessageEdited.Event = await conversation.wait_event(MessageEdited())
    response: Message = event.message
    assert "send me the title" in response.message
    await conversation.send_message(f"{prefix}Test tour")

    response: Message = await conversation.get_response()
    assert "send me the description" in response.message
    await conversation.send_message(f"{prefix}Test tour description")

    response: Message = await conversation.get_response()
    assert "title for the new section" in response.message

    await conversation.send_message(f"{prefix}Section 1")
    response: Message = await conversation.get_response()
    assert "Now send me a" in response.message

    await conversation.send_message(f"{prefix}Content 1")
    response: Message = await conversation.get_response()
    assert "text was added" in response.message

    await conversation.send_message(f"{prefix}Content 2")
    response: Message = await conversation.get_response()
    assert "text was added" in response.message

    await conversation.send_message("/done")
    response: Message = await conversation.get_response()
    assert "Send me the title of the next tour section" in response.message

    await conversation.send_message(f"{prefix}Section 2")
    response: Message = await conversation.get_response()
    assert "Now send me a" in response.message

    await conversation.send_message(f"{prefix}Content 3")
    response: Message = await conversation.get_response()
    assert "text was added" in response.message

    await conversation.send_message(f"{prefix}Content 4")
    response: Message = await conversation.get_response()
    assert "text was added" in response.message

    await conversation.send_message("/done")
    response: Message = await conversation.get_response()
    assert "Send me the title of the next tour section" in response.message

    await conversation.send_message("/done")
    response: Message = await conversation.get_response()
    assert "Done" in response.message


def check_tour(
    tour: Tour | None,
    language: str,
    translation_id: int = 0,
    prefix: str = "",
    markdown_prefix: str = "",
):
    assert tour is not None
    assert len(tour.translations) > translation_id
    assert tour.translations[translation_id].language == language
    assert tour.translations[translation_id].title == f"{prefix}Test tour"
    assert (
        tour.translations[translation_id].description
        == f"{markdown_prefix}Test tour description"
    )
    assert tour.translations[translation_id].sections[0].title == f"{prefix}Section 1"
    assert tour.translations[translation_id].sections[0].position == 0
    assert tour.translations[translation_id].sections[0].content[0].content == {
        "text": f"{markdown_prefix}Content 1"
    }
    assert tour.translations[translation_id].sections[0].content[0].position == 0
    assert tour.translations[translation_id].sections[0].content[1].content == {
        "text": f"{markdown_prefix}Content 2"
    }
    assert tour.translations[translation_id].sections[0].content[1].position == 1
    assert tour.translations[translation_id].sections[1].title == f"{prefix}Section 2"
    assert tour.translations[translation_id].sections[1].position == 1
    assert tour.translations[translation_id].sections[1].content[0].content == {
        "text": f"{markdown_prefix}Content 3"
    }
    assert tour.translations[translation_id].sections[1].content[0].position == 0
    assert tour.translations[translation_id].sections[1].content[1].content == {
        "text": f"{markdown_prefix}Content 4"
    }
    assert tour.translations[translation_id].sections[1].content[1].position == 1


@pytest.mark.usefixtures("app", "guest")
@pytest.mark.enabled_languages("en")
async def test_adding_one_tour_single_language(
    admin_conversation: Conversation, db_engine: AsyncEngine
):
    conversation = admin_conversation
    await conversation.send_message("/tours")
    response: Message = await conversation.get_response()
    assert "select an action" in response.message
    assert await response.click(text="Add a tour") is not None

    await add_tour(conversation)

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        stmt = select(Tour).options(
            selectinload(Tour.translations)
            .selectinload(TourTranslation.sections)
            .selectinload(TourSection.content)
        )
        tour = await session.scalar(stmt)

    check_tour(tour, "en")


@pytest.mark.usefixtures("app", "guest")
@pytest.mark.enabled_languages("en")
async def test_adding_two_tours_single_language(
    admin_conversation: Conversation, db_engine: AsyncEngine
):
    conversation = admin_conversation
    await conversation.send_message("/tours")
    response: Message = await conversation.get_response()
    assert "select an action" in response.message
    assert await response.click(text="Add a tour") is not None

    await add_tour(conversation)

    await conversation.send_message("/tours")
    response: Message = await conversation.get_response()
    assert await response.click(text="Add a tour") is not None

    await add_tour(conversation, "(2) ")

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        stmt = (
            select(Tour)
            .options(
                selectinload(Tour.translations)
                .selectinload(TourTranslation.sections)
                .selectinload(TourSection.content)
            )
            .order_by(Tour.id)
        )
        tours = (await session.scalars(stmt)).all()

    assert len(tours) == 2

    check_tour(tours[0], "en")
    check_tour(tours[1], "en", 0, "(2) ", r"\(2\) ")


@pytest.mark.usefixtures("app", "guest", "tours")
@pytest.mark.enabled_languages("en")
async def test_adding_second_tour_single_language(
    admin_conversation: Conversation, db_engine: AsyncEngine
):
    conversation = admin_conversation
    await conversation.send_message("/tours")
    response: Message = await conversation.get_response()
    assert "select an action" in response.message
    assert await response.click(text="Add a tour") is not None

    await add_tour(conversation, "(2) ")

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        stmt = (
            select(Tour)
            .options(
                selectinload(Tour.translations)
                .selectinload(TourTranslation.sections)
                .selectinload(TourSection.content)
            )
            .order_by(Tour.id)
        )
        tours = (await session.scalars(stmt)).all()

    assert len(tours) == 2

    check_tour(tours[1], "en", 0, "(2) ", r"\(2\) ")


@pytest.mark.usefixtures("app", "guest")
@pytest.mark.enabled_languages("en", "ru")
async def test_adding_one_tour_multilang(
    admin_conversation: Conversation, db_engine: AsyncEngine
):
    conversation = admin_conversation
    await conversation.send_message("/tours")
    response: Message = await conversation.get_response()
    assert "select an action" in response.message
    assert await response.click(text="Add a tour") is not None

    event: MessageEdited.Event = await conversation.wait_event(MessageEdited())
    response: Message = event.message
    assert "select the language" in response.message
    assert await response.click(text="English") is not None

    await add_tour(conversation)

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        stmt = select(Tour).options(
            selectinload(Tour.translations)
            .selectinload(TourTranslation.sections)
            .selectinload(TourSection.content)
        )
        tour = await session.scalar(stmt)

    check_tour(tour, "en")
