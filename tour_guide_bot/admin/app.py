from tour_guide_bot.helpers.telegram import Application
from tour_guide_bot.helpers.language import LanguageHandler
from .start import StartCommandHandler
from .configure import ConfigureCommandHandler
from .tour import TourCommandHandler


class AdminBot(Application):
    async def initialize(self) -> None:
        self.add_handlers(StartCommandHandler.get_handlers())
        self.add_handlers(ConfigureCommandHandler.get_handlers())
        self.add_handlers(TourCommandHandler.get_handlers())
        self.add_handlers(LanguageHandler.get_handlers())

        await super().initialize()
