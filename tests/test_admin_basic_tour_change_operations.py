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


@pytest.fixture
async def tours_as_dicts(default_tour: dict) -> list[dict]:
    return [default_tour, default_tour, default_tour]


@pytest.mark.usefixtures("app", "guest", "tours")
@pytest.mark.enabled_languages("en")
async def test_delete_tour(admin_conversation: Conversation, db_engine: AsyncEngine):
    conversation = admin_conversation
    await conversation.send_message("/tours")
    response: Message = await conversation.get_response()

    assert await response.click(text="Delete a tour") is not None
    event: MessageEdited.Event = await conversation.wait_event(MessageEdited())
    response: Message = event.message

    assert await response.click(1) is not None
    event: MessageEdited.Event = await conversation.wait_event(MessageEdited())
    response: Message = event.message

    assert await response.click(text="Yes") is not None
    event: MessageEdited.Event = await conversation.wait_event(MessageEdited())
    response: Message = event.message

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
    assert tours[0].id == 1
    assert tours[1].id == 3


@pytest.mark.usefixtures("app", "guest", "tours")
@pytest.mark.enabled_languages("en")
async def test_not_deleted_if_said_no(
    admin_conversation: Conversation, db_engine: AsyncEngine
):
    conversation = admin_conversation
    await conversation.send_message("/tours")
    response: Message = await conversation.get_response()

    assert await response.click(text="Delete a tour") is not None
    event: MessageEdited.Event = await conversation.wait_event(MessageEdited())
    response: Message = event.message

    assert await response.click(1) is not None
    event: MessageEdited.Event = await conversation.wait_event(MessageEdited())
    response: Message = event.message

    assert await response.click(text="Abort") is not None
    event: MessageEdited.Event = await conversation.wait_event(MessageEdited())
    response: Message = event.message

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

    assert len(tours) == 3
    assert tours[0].id == 1
    assert tours[1].id == 2
    assert tours[2].id == 3
