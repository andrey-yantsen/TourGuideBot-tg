from tour_guide_bot.bot.app import Application


async def test_init_works(unintialized_app: Application):
    await unintialized_app.initialize()
    assert unintialized_app._initialized == True


async def test_init_test_app_works(unitialized_test_app: Application):
    await unitialized_test_app.initialize()
    assert unitialized_test_app._initialized == True
