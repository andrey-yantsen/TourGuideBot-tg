from telegram import Update
from telegram.ext import ContextTypes, TypeHandler, Application as BotApplication
from . import log


class Application(BotApplication):
    @classmethod
    def builder(cls):
        builder = super().builder()
        builder.application_class(cls)
        return builder

    async def initialize(self) -> None:
        self.add_handler(TypeHandler(object, self.debug_log_handler), -1)
        await super().initialize()

    async def debug_log_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        log.debug('[{0}] received update: {1}'.format(context.application.__class__.__name__, update))
