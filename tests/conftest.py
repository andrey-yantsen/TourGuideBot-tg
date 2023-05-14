import asyncio
from os import environ

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from telegram.ext import ContextTypes

from tour_guide_bot.bot.app import Application
from tour_guide_bot.cli import prepare_app


@pytest.fixture(scope="session")
def bot_token() -> str:
    token = environ.get("TOUR_GUIDE_TELEGRAM_BOT_TOKEN")
    assert (
        token
    ), "Please set the telegram bot token via TOUR_GUIDE_TELEGRAM_BOT_TOKEN env variable"
    return token


@pytest.fixture(scope="session")
def persistence_path(tmp_path_factory: pytest.TempPathFactory) -> str:
    return str(tmp_path_factory.mktemp("persistence"))


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db_engine(persistence_path):
    from tour_guide_bot.models import Base
    import tour_guide_bot.models.admin as _  # noqa: F811, F401
    import tour_guide_bot.models.guide as _  # noqa: F811, F401
    import tour_guide_bot.models.settings as _  # noqa: F811, F401
    import tour_guide_bot.models.telegram as _  # noqa: F811, F401

    engine = create_async_engine(
        "sqlite+aiosqlite:///{}/{}".format(
            persistence_path,
            "test.db",
        )
    )

    with create_engine(
        "sqlite:///{}/{}".format(
            persistence_path,
            "test.db",
        )
    ).connect() as connection:
        Base.metadata.create_all(connection)

        yield engine

        Base.metadata.drop_all(connection)


@pytest.fixture(scope="session")
def enabled_languages() -> list[str]:
    return ["en"]


@pytest.fixture(scope="session")
def default_language() -> str:
    return "en"


@pytest.fixture
def unintialized_app(
    bot_token, db_engine, enabled_languages, default_language, persistence_path
) -> Application:
    return prepare_app(
        bot_token, db_engine, enabled_languages, default_language, persistence_path
    )


@pytest_asyncio.fixture
async def app(unintialized_app: Application) -> Application:
    await unintialized_app.initialize()
    return unintialized_app


class TestApplication(Application):
    async def check_new_approved_tours(
        self, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        pass


@pytest.fixture
def unitialized_test_app(
    bot_token, db_engine, enabled_languages, default_language, persistence_path
) -> TestApplication:
    return prepare_app(
        bot_token,
        db_engine,
        enabled_languages,
        default_language,
        persistence_path,
        TestApplication,
    )


@pytest_asyncio.fixture
async def test_app(test_unitialized_app: TestApplication) -> TestApplication:
    await test_unitialized_app.initialize()
    return test_unitialized_app
