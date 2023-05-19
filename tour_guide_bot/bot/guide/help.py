from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import BaseHandlerCallback
from tour_guide_bot.models.settings import Settings, SettingsKey


class HelpCommandHandler(BaseHandlerCallback):
    @classmethod
    def get_handlers(cls):
        return [
            CommandHandler("help", cls.partial(cls.help)),
            CommandHandler("terms", cls.partial(cls.terms)),
            CommandHandler("support", cls.partial(cls.support)),
        ]

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        language = await self.get_language(update, context)

        await update.message.reply_text(
            t(language).pgettext(
                "guest-help",
                "You can use the following commands:\n"
                "* /start — to see the welcome message again\n"
                "* /tours — to list all the available for you tours\n"
                "* /terms — display terms & conditions\n"
                "* /support — to see how to contact the support\n"
                "* /language — to change the interface language",
            )
        )

    async def terms(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        language = await self.get_language(update, context)
        terms = await Settings.load(
            self.db_session, SettingsKey.terms_message, language
        )

        if terms is None:
            await update.message.reply_text(
                t(language).pgettext(
                    "guest-help",
                    "There are no terms & conditions yet. Please, try again later.",
                )
            )
            return

        await update.message.reply_markdown_v2(terms.value)

    async def support(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        language = await self.get_language(update, context)

        support = await Settings.load(
            self.db_session, SettingsKey.support_message, language
        )

        if support is None:
            await update.message.reply_text(
                t(language).pgettext(
                    "guest-help",
                    "There are no support details yet. Please, try again later.",
                )
            )
            return

        await update.message.reply_markdown_v2(support.value)
