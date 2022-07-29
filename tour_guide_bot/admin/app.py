from telegram.ext import Application, CommandHandler
from .start import StartCommandHandler


class AdminBot(Application):
    @classmethod
    def builder(cls):
        builder = super().builder()
        builder.application_class(cls)
        return builder

    async def initialize(self) -> None:
        self.add_handler(StartCommandHandler.get_handler(self, self.db_engine))

        await super().initialize()
