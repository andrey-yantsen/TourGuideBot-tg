from tour_guide_bot.bot.app import Application


async def test_init_works(unitialized_app: Application):
    await unitialized_app.initialize()
    assert unitialized_app._initialized == True
