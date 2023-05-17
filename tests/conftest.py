import asyncio
from os import environ
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.custom.conversation import Conversation
from telethon.tl.types import KeyboardButtonRequestPhone

from tour_guide_bot.bot.app import Application
from tour_guide_bot.cli import prepare_app
from tour_guide_bot.models.admin import Admin, AdminPermissions
from tour_guide_bot.models.guide import Guest
from tour_guide_bot.models.settings import Settings, SettingsKey
from tour_guide_bot.models.telegram import TelegramUser


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def bot_token() -> str:
    token = environ.get("TOUR_GUIDE_TELEGRAM_BOT_TOKEN")
    assert (
        token
    ), "Please set the telegram bot token via TOUR_GUIDE_TELEGRAM_BOT_TOKEN env variable"
    return token


@pytest.fixture(scope="session")
def mtproto_api_id():
    api_id = environ.get("TOUR_GUIDE_TELEGRAM_APP_API_ID")
    assert (
        api_id
    ), "Please set the telegram app api id via TOUR_GUIDE_TELEGRAM_APP_API_ID env variable"
    return api_id


@pytest.fixture(scope="session")
def mtproto_api_hash():
    api_hash = environ.get("TOUR_GUIDE_TELEGRAM_APP_API_HASH")
    assert (
        api_hash
    ), "Please set the telegram app api hash via TOUR_GUIDE_TELEGRAM_APP_API_HASH env variable"
    return api_hash


@pytest.fixture(scope="session")
def mtproto_session_string() -> StringSession:
    session_string = environ.get("TOUR_GUIDE_TELEGRAM_APP_SESSION_STRING")

    assert (
        session_string
    ), "Please set the telegram app session string via TOUR_GUIDE_TELEGRAM_APP_SESSION_STRING env variable (see readme on how to get it)"
    return StringSession(session_string)


@pytest.fixture
def persistence_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("persistence")


@pytest.fixture
def test_db_file(persistence_path: Path) -> Path:
    return persistence_path.joinpath("test.db")


@pytest.fixture
async def db_engine(test_db_file: Path):
    import tour_guide_bot.models.admin as _admin  # noqa: F401
    import tour_guide_bot.models.guide as _guite  # noqa: F401
    import tour_guide_bot.models.settings as _settings  # noqa: F401
    import tour_guide_bot.models.telegram as _telegram  # noqa: F401
    from tour_guide_bot.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///{}".format(test_db_file))

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield engine


@pytest.fixture
def enabled_languages(request: pytest.FixtureRequest) -> list[str]:
    marker = request.node.get_closest_marker("enabled_languages")
    if marker is None:
        data = ["en", "ru"]
    else:
        data = marker.args[0]

    return data


@pytest.fixture
def default_language() -> str:
    return "en"


@pytest.fixture
def unitialized_app(
    bot_token: str,
    db_engine: AsyncEngine,
    enabled_languages: list[str],
    default_language: str,
    persistence_path: Path,
):
    app = prepare_app(
        bot_token, db_engine, enabled_languages, default_language, str(persistence_path)
    )

    yield app


@pytest.fixture
async def unconfigured_app(unitialized_app: Application):
    await unitialized_app.initialize()
    if unitialized_app.post_init:
        await unitialized_app.post_init()
    await unitialized_app.updater.start_polling()
    await unitialized_app.start()

    yield unitialized_app

    await unitialized_app.updater.stop()
    await unitialized_app.stop()

    await asyncio.sleep(2)


@pytest.fixture
async def app(unconfigured_app: Application, db_engine: AsyncEngine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        welcome_message = Settings(
            key=SettingsKey.guide_welcome_message, language="en", value="welcome"
        )
        session.add(welcome_message)
        await session.commit()

    yield unconfigured_app


@pytest.fixture(scope="session")
async def telegram_client(
    mtproto_api_id: str, mtproto_api_hash: str, mtproto_session_string: StringSession
):
    client = TelegramClient(
        mtproto_session_string,
        mtproto_api_id,
        mtproto_api_hash,
        sequential_updates=True,
        flood_sleep_threshold=60,
    )
    await client.connect()
    await client.get_me()
    await client.get_dialogs()

    yield client

    await client.disconnect()
    await client.disconnected


@pytest.fixture(scope="session")
def bot_id(bot_token: str) -> int:
    return int(bot_token.split(":")[0])


class ConversationWrapper:
    def __init__(self, wrappee: Conversation):
        self.wrappee = wrappee

    def __getattr__(self, attr):
        return getattr(self.wrappee, attr)

    async def send_message(self, *args, **kwargs):
        ret = await self.wrappee.send_message(*args, **kwargs)
        await asyncio.sleep(1)
        return ret

    async def send_file(self, *args, **kwargs):
        ret = await self.wrappee.send_file(*args, **kwargs)
        await asyncio.sleep(1)
        return ret

    async def wait_event(self, event, *, timeout=None):
        ret = await self.wrappee.wait_event(event, timeout=timeout)
        await asyncio.sleep(1)
        return ret


@pytest.fixture(scope="session")
async def conversation(telegram_client: TelegramClient, bot_id: int):
    async with telegram_client.conversation(
        bot_id, timeout=10, max_messages=10000
    ) as conv:
        yield ConversationWrapper(conv)


async def get_telegram_user(
    user_id: int, language: str, session: AsyncSession
) -> TelegramUser:
    stmt = (
        select(TelegramUser)
        .where(TelegramUser.id == user_id)
        .options(selectinload(TelegramUser.admin), selectinload(TelegramUser.guest))
    )
    user = await session.scalar(stmt)

    if not user:
        user = TelegramUser(id=user_id, language=language)

    return user


@pytest.fixture
async def guest(
    db_engine: AsyncEngine, telegram_client: TelegramClient, default_language: str
):
    me = await telegram_client.get_me()
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        guest = Guest(phone=me.phone)
        telegram_user = await get_telegram_user(me.id, default_language, session)
        telegram_user.guest = guest

        session.add(guest)
        session.add(telegram_user)
        await session.commit()

        return guest


@pytest.fixture
async def admin(
    db_engine: AsyncEngine,
    telegram_client: TelegramClient,
    default_language: str,
):
    me = await telegram_client.get_me()
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        admin = Admin(phone=me.phone, permissions=AdminPermissions.full)
        telegram_user = await get_telegram_user(me.id, default_language, session)
        telegram_user.admin = admin

        session.add(admin)
        session.add(telegram_user)
        await session.commit()

        return admin


@pytest.fixture
async def admin_conversation(conversation: Conversation, app, admin):
    await conversation.send_message("/admin")
    response = await conversation.get_response()

    assert (
        "Welcome to the admin mode" in response.message
    ), "Unexpected message in response to the admin mode switch"

    await asyncio.sleep(0.5)

    yield conversation


async def get_phone_number_request(conversation: Conversation):
    response = await conversation.get_response()
    assert response.reply_markup is not None, "No reply markup"
    assert response.reply_markup.rows, "No reply markup rows"
    assert response.reply_markup.rows[0].buttons, "No reply markup buttons"
    assert isinstance(
        response.reply_markup.rows[0].buttons[0], KeyboardButtonRequestPhone
    ), "No request phone button"
    return response
