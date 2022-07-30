from tour_guide_bot.helpers.telegram import Application
from tour_guide_bot.helpers.language import LanguageHandler
from .start import StartCommandHandler


class GuideBot(Application):
    async def initialize(self) -> None:
        self.add_handlers(StartCommandHandler.get_handlers())
        self.add_handlers(LanguageHandler.get_handlers())

        await super().initialize()
