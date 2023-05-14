from os import environ
from pathlib import Path

import pytest
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


@pytest.fixture(scope="function")
def persistence_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("persistence")


@pytest.fixture
def test_db_file(persistence_path: Path) -> Path:
    return persistence_path.joinpath("test.db")


@pytest.fixture
async def db_engine(test_db_file: Path):
    from tour_guide_bot.models import Base
    import tour_guide_bot.models.admin as _  # noqa: F811, F401
    import tour_guide_bot.models.guide as _  # noqa: F811, F401
    import tour_guide_bot.models.settings as _  # noqa: F811, F401
    import tour_guide_bot.models.telegram as _  # noqa: F811, F401

    engine = create_async_engine("sqlite+aiosqlite:///{}".format(test_db_file))

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


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
        bot_token, db_engine, enabled_languages, default_language, str(persistence_path)
    )


@pytest.fixture
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
        str(persistence_path),
        TestApplication,
    )


@pytest.fixture
async def test_app(test_unitialized_app: TestApplication) -> TestApplication:
    await test_unitialized_app.initialize()
    return test_unitialized_app
