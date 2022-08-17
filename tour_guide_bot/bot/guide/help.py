from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import BaseHandlerCallback


class HelpCommandHandler(BaseHandlerCallback):
    @classmethod
    def get_handlers(cls):
        return [
            CommandHandler("help", cls.partial(cls.help)),
        ]

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        language = await self.get_language(update, context)

        await update.message.reply_text(
            t(language).pgettext(
                "guest-help",
                "You can use the following commands:\n"
                "* /start — to see the welcome message again\n"
                "* /tours — to list all the available for you tours\n"
                "* /language — to change the interface language",
            )
        )
