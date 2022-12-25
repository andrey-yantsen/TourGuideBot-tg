from warnings import filterwarnings

import pytest
from telegram.warnings import PTBUserWarning

from tour_guide_bot.bot.app import Application


async def test_init_works(app: Application):
    await app.initialize()

    assert app._initialized == True


async def test_init_test_app_works(test_app: Application):
    await test_app.initialize()

    assert test_app._initialized == True
