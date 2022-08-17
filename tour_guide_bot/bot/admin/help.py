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

    async def waiting_contact_help(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)

        await update.message.reply_text(
            t(language).pgettext("admin-help", "Please send me your contact.")
        )

    async def waiting_token_help(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)

        await update.message.reply_text(
            t(language).pgettext("admin-help", "Please send me the magic word.")
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        language = await self.get_language(update, context)

        await update.message.reply_text(
            t(language).pgettext(
                "admin-help",
                "You can use the following commands:\n"
                "* /start — to see the welcome message again\n"
                "* /configure — to change the bot's settings\n"
                "* /tours — to manage your tours\n"
                "* /approve — to allow the access to a tour to somebody\n"
                "* /revoke — to revoke somebody's access to a tour\n"
                "* /language — to change the interface language",
            )
        )
