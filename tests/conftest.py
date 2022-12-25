import asyncio
from os import environ

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from telegram.ext import ContextTypes

from tour_guide_bot.bot.app import Application
from tour_guide_bot.cli import prepare_app


@pytest.fixture
def bot_token() -> str:
    bot_token = environ.get("TOUR_GUIDE_TELEGRAM_BOT_TOKEN")
    assert bot_token
    return bot_token


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
    import tour_guide_bot.models.admin as _
    import tour_guide_bot.models.guide as _
    import tour_guide_bot.models.settings as _
    import tour_guide_bot.models.telegram as _

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
        Base.metadata.bind = connection
        Base.metadata.create_all()

        yield engine

        Base.metadata.drop_all()


@pytest.fixture
def enabled_languages() -> list[str]:
    return ["en"]


@pytest.fixture
def default_language() -> str:
    return "en"


@pytest.fixture
def app(bot_token, db_engine, enabled_languages, default_language, persistence_path):
    return prepare_app(
        bot_token, db_engine, enabled_languages, default_language, persistence_path
    )


class TestApplication(Application):
    async def check_new_approved_tours(
        self, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        pass


@pytest.fixture
def test_app(
    bot_token, db_engine, enabled_languages, default_language, persistence_path
):
    return prepare_app(
        bot_token,
        db_engine,
        enabled_languages,
        default_language,
        persistence_path,
        TestApplication,
    )
