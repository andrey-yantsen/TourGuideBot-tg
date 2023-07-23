import pytest
from sqlalchemy import Sequence, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from telethon.events import MessageEdited
from telethon.tl.custom import Message
from telethon.tl.custom.conversation import Conversation

from tour_guide_bot.models.guide import Product


@pytest.mark.usefixtures("app", "admin")
async def test_menu_not_available_without_tours(
    admin_conversation: Conversation,
):
    await admin_conversation.send_message("/tours")
    response: Message = await admin_conversation.get_response()

    assert response.reply_markup
    assert len(response.reply_markup.rows) == 2

    assert response.reply_markup.rows[0].buttons[0].text == "Add a tour"
    assert response.reply_markup.rows[1].buttons[0].text == "Abort"


@pytest.mark.skip_payment_token_stub
@pytest.mark.usefixtures("app", "admin", "tours")
async def test_menu_available_without_configured_payments(
    admin_conversation: Conversation,
):
    await admin_conversation.send_message("/tours")
    response: Message = await admin_conversation.get_response()

    assert response.reply_markup
    assert len(response.reply_markup.rows) == 4

    assert response.reply_markup.rows[0].buttons[0].text == "Add a tour"
    assert response.reply_markup.rows[1].buttons[0].text == "Manage pricing"
    assert response.reply_markup.rows[2].buttons[0].text == "Delete a tour"
    assert response.reply_markup.rows[3].buttons[0].text == "Abort"

    assert await response.click(text="Manage pricing") is not None

    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "configure payment providers before" in msg.message


@pytest.mark.enabled_languages("en")
@pytest.mark.skip_adding_products
@pytest.mark.usefixtures("app", "admin", "tours")
async def test_add_price_single_language(
    admin_conversation: Conversation, db_engine: AsyncEngine
):
    await admin_conversation.send_message("/tours")
    response: Message = await admin_conversation.get_response()
    assert await response.click(text="Manage pricing") is not None

    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert await msg.click(text="Add a new product") is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "Please select the tour" in msg.message

    assert await msg.click(0) is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "send me the number of guests" in msg.message

    await admin_conversation.send_message("1")
    response: Message = await admin_conversation.get_response()

    assert "send me the currency" in response.message

    await admin_conversation.send_message("GBP")
    response: Message = await admin_conversation.get_response()

    assert "send me the price" in response.message

    await admin_conversation.send_message("12.34")
    response: Message = await admin_conversation.get_response()

    assert "£12.34 should buy?" in response.message

    await admin_conversation.send_message("88")
    response: Message = await admin_conversation.get_response()

    assert "send me the title" in response.message

    await admin_conversation.send_message("Purchase title")
    response: Message = await admin_conversation.get_response()

    assert "send me the description" in response.message

    await admin_conversation.send_message("Purchase description")
    response: Message = await admin_conversation.get_response()

    assert "users can buy" in response.message
    assert "88-" in response.message
    assert "£12.34" in response.message
    assert "for 1 guest" in response.message

    await admin_conversation.send_message("/tours")
    response: Message = await admin_conversation.get_response()
    assert await response.click(text="Manage pricing") is not None

    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert await msg.click(text="Add a new product") is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "Please select the tour" in msg.message

    assert await msg.click(0) is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "send me the number of guests" in msg.message

    await admin_conversation.send_message("2")
    response: Message = await admin_conversation.get_response()

    assert "send me the currency" in response.message

    await admin_conversation.send_message("USD")
    response: Message = await admin_conversation.get_response()

    assert "send me the price" in response.message

    await admin_conversation.send_message("56.78")
    response: Message = await admin_conversation.get_response()

    assert "$56.78 should buy?" in response.message

    await admin_conversation.send_message("77")
    response: Message = await admin_conversation.get_response()

    assert "send me the title" in response.message

    await admin_conversation.send_message("Purchase title 2")
    response: Message = await admin_conversation.get_response()

    assert "send me the description" in response.message

    await admin_conversation.send_message("Purchase description 2")
    response: Message = await admin_conversation.get_response()

    assert "users can buy" in response.message
    assert "77-" in response.message
    assert "$56.78" in response.message
    assert "for 2 guests" in response.message

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        stmt = select(Product)
        products: Sequence[Product] = (await session.scalars(stmt)).all()

        assert len(products) == 2

        assert products[0].available
        assert products[0].guests == 1
        assert products[0].currency == "GBP"
        assert products[0].language == "en"
        assert products[0].price == 1234
        assert products[0].title == "Purchase title"
        assert products[0].description == "Purchase description"

        assert products[1].available
        assert products[1].guests == 2
        assert products[1].currency == "USD"
        assert products[1].language == "en"
        assert products[1].price == 5678
        assert products[1].title == "Purchase title 2"
        assert products[1].description == "Purchase description 2"


@pytest.mark.enabled_languages("en", "ru")
@pytest.mark.skip_adding_products
@pytest.mark.usefixtures("app", "admin", "tours")
async def test_add_price_multiple_languages(
    admin_conversation: Conversation, db_engine: AsyncEngine
):
    await admin_conversation.send_message("/tours")
    response: Message = await admin_conversation.get_response()
    assert await response.click(text="Manage pricing") is not None

    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert await msg.click(text="Add a new product") is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "Please select the tour" in msg.message

    assert await msg.click(0) is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "select the language" in msg.message

    assert await msg.click(text="English") is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "send me the number of guests" in msg.message

    await admin_conversation.send_message("1")
    response: Message = await admin_conversation.get_response()

    assert "send me the currency" in response.message

    await admin_conversation.send_message("GBP")
    response: Message = await admin_conversation.get_response()

    assert "send me the price" in response.message

    await admin_conversation.send_message("12.34")
    response: Message = await admin_conversation.get_response()

    assert "£12.34 should buy?" in response.message

    await admin_conversation.send_message("88")
    response: Message = await admin_conversation.get_response()

    assert "send me the title" in response.message

    await admin_conversation.send_message("Purchase title")
    response: Message = await admin_conversation.get_response()

    assert "send me the description" in response.message

    await admin_conversation.send_message("Purchase description")
    response: Message = await admin_conversation.get_response()

    assert "users can buy" in response.message
    assert "88-" in response.message
    assert "£12.34" in response.message
    assert "for 1 guest" in response.message

    await admin_conversation.send_message("/tours")
    response: Message = await admin_conversation.get_response()
    assert await response.click(text="Manage pricing") is not None

    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert await msg.click(text="Add a new product") is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "Please select the tour" in msg.message

    assert await msg.click(0) is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "select the language" in msg.message

    assert await msg.click(text="Russian") is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "send me the number of guests" in msg.message

    await admin_conversation.send_message("2")
    response: Message = await admin_conversation.get_response()

    assert "send me the currency" in response.message

    await admin_conversation.send_message("RUB")
    response: Message = await admin_conversation.get_response()

    assert "send me the price" in response.message

    await admin_conversation.send_message("345.67")
    response: Message = await admin_conversation.get_response()

    assert "345,67 RUB should buy?" in response.message

    await admin_conversation.send_message("100")
    response: Message = await admin_conversation.get_response()

    assert "send me the title" in response.message

    await admin_conversation.send_message("Purchase title 2")
    response: Message = await admin_conversation.get_response()

    assert "send me the description" in response.message

    await admin_conversation.send_message("Purchase description 2")
    response: Message = await admin_conversation.get_response()

    assert "users can buy" in response.message
    assert "100-" in response.message
    assert "345,67 RUB" in response.message
    assert "for 2 guests" in response.message

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        stmt = select(Product)
        products: Sequence[Product] = (await session.scalars(stmt)).all()

        assert len(products) == 2

        assert products[0].available
        assert products[0].guests == 1
        assert products[0].currency == "GBP"
        assert products[0].language == "en"
        assert products[0].price == 1234
        assert products[0].duration_days == 88
        assert products[0].title == "Purchase title"
        assert products[0].description == "Purchase description"

        assert products[1].available
        assert products[1].guests == 2
        assert products[1].currency == "RUB"
        assert products[1].language == "ru"
        assert products[1].price == 34567
        assert products[1].duration_days == 100
        assert products[1].title == "Purchase title 2"
        assert products[1].description == "Purchase description 2"


@pytest.mark.products_count_in_default_tour(2)
@pytest.mark.enabled_languages("en")
@pytest.mark.usefixtures("app", "admin", "tours")
async def test_update_price_single_language(
    admin_conversation: Conversation, db_engine: AsyncEngine
):
    await admin_conversation.send_message("/tours")
    response: Message = await admin_conversation.get_response()
    assert await response.click(text="Manage pricing") is not None

    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert await msg.click(text="Update a product") is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "Please select the tour" in msg.message

    assert await msg.click(0) is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "select the product" in msg.message

    assert await msg.click(0) is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "send me the number of guests" in msg.message

    await admin_conversation.send_message("2")
    response: Message = await admin_conversation.get_response()

    assert "send me the currency" in response.message

    await admin_conversation.send_message("GBP")
    response: Message = await admin_conversation.get_response()

    assert "send me the price" in response.message

    await admin_conversation.send_message("12.34")
    response: Message = await admin_conversation.get_response()

    assert "£12.34 should buy?" in response.message

    await admin_conversation.send_message("88")
    response: Message = await admin_conversation.get_response()

    assert "send me the title" in response.message

    await admin_conversation.send_message("Purchase title")
    response: Message = await admin_conversation.get_response()

    assert "send me the description" in response.message

    await admin_conversation.send_message("Purchase description")
    response: Message = await admin_conversation.get_response()

    assert "users can buy" in response.message
    assert "88-" in response.message
    assert "£12.34" in response.message
    assert "for 2 guests" in response.message

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        stmt = select(Product).order_by(Product.id)
        products: Sequence[Product] = (await session.scalars(stmt)).all()

        assert len(products) == 3

        assert not products[0].available

        assert products[1].available
        assert products[1].guests == 1
        assert products[1].currency == "USD"
        assert products[1].language == "en"

        assert products[2].available
        assert products[2].guests == 2
        assert products[2].currency == "GBP"
        assert products[2].language == "en"
        assert products[2].price == 1234
        assert products[2].duration_days == 88
        assert products[2].title == "Purchase title"
        assert products[2].description == "Purchase description"


@pytest.mark.products_count_in_default_tour(2)
@pytest.mark.enabled_languages("en")
@pytest.mark.usefixtures("app", "admin", "tours")
async def test_delete_price_single_language(
    admin_conversation: Conversation, db_engine: AsyncEngine
):
    await admin_conversation.send_message("/tours")
    response: Message = await admin_conversation.get_response()
    assert await response.click(text="Manage pricing") is not None

    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert await msg.click(text="Delete a product") is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "Please select the tour" in msg.message

    assert await msg.click(0) is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "select the product" in msg.message

    assert await msg.click(0) is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert await msg.click(text="Yes") is not None

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        stmt = select(Product).order_by(Product.id)
        products: Sequence[Product] = (await session.scalars(stmt)).all()

        assert len(products) == 2

        assert not products[0].available
        assert products[0].duration_days == 1

        assert products[1].available
        assert products[1].guests == 1
        assert products[1].duration_days == 2
        assert products[1].currency == "USD"
        assert products[1].language == "en"


@pytest.mark.products_count_in_default_tour(2)
@pytest.mark.enabled_languages("en", "ru")
@pytest.mark.usefixtures("app", "admin", "tours")
async def test_delete_price_multiple_language(
    admin_conversation: Conversation, db_engine: AsyncEngine
):
    await admin_conversation.send_message("/tours")
    response: Message = await admin_conversation.get_response()
    assert await response.click(text="Manage pricing") is not None

    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert await msg.click(text="Delete a product") is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "Please select the tour" in msg.message

    assert await msg.click(0) is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "select the language" in msg.message

    assert await msg.click(text="English") is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "select the product" in msg.message

    assert await msg.click(0) is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert await msg.click(text="Yes") is not None

    await admin_conversation.send_message("/tours")
    response: Message = await admin_conversation.get_response()
    assert await response.click(text="Manage pricing") is not None

    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert await msg.click(text="Delete a product") is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "Please select the tour" in msg.message

    assert await msg.click(0) is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "select the language" in msg.message

    assert await msg.click(text="Russian") is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert "select the product" in msg.message

    assert await msg.click(1) is not None
    event: MessageEdited.Event = await admin_conversation.wait_event(MessageEdited())
    msg: Message = event.message

    assert await msg.click(text="Yes") is not None

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        stmt = select(Product).order_by(Product.id)
        products: Sequence[Product] = (await session.scalars(stmt)).all()

        assert len(products) == 4

        assert not products[0].available
        assert products[0].duration_days == 1

        assert products[1].available
        assert products[1].guests == 1
        assert products[1].duration_days == 2
        assert products[1].currency == "USD"
        assert products[1].language == "en"

        assert products[2].available
        assert products[2].guests == 1
        assert products[2].duration_days == 1
        assert products[2].currency == "USD"
        assert products[2].language == "ru"

        assert not products[3].available
        assert products[3].guests == 1
        assert products[3].duration_days == 2
        assert products[3].currency == "USD"
        assert products[3].language == "ru"
