from telegram.ext import Application
from tour_guide_bot.helpers.language import LanguageHandler
from .start import StartCommandHandler


class AdminBot(Application):
    @classmethod
    def builder(cls):
        builder = super().builder()
        builder.application_class(cls)
        return builder

    async def initialize(self) -> None:
        self.add_handlers(StartCommandHandler.get_handlers(self.db_engine))
        self.add_handlers(LanguageHandler.get_handlers(self.db_engine))

        await super().initialize()
