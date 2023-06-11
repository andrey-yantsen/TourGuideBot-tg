from babel import Locale
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from tour_guide_bot import t
from tour_guide_bot.helpers.language_selector import SelectLanguageHandler


class LanguageHandler(SelectLanguageHandler):
    LANGUAGE_SELECTION_LANGUAGE_FRIENDLY = True

    @classmethod
    def get_handlers(cls) -> list:
        return [
            CommandHandler("language", cls.partial(cls.start)),
            *cls.get_select_language_handlers(),
        ]

    async def after_language_selected(
        self,
        language: str,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_language: bool,
    ):
        user = await self.get_user(update, context)
        user.language = language
        self.db_session.add(user)
        await self.db_session.commit()

        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            t(language)
            .pgettext("bot-generic", "The language has been changed to {0}.")
            .format(Locale.parse(language).get_language_name(language))
        )

    def get_language_selection_message(self, user_language: str) -> str:
        return t(user_language).pgettext(
            "bot-generic", "Please select the language you prefer"
        )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        current_language = await self.get_language(update, context)

        if len(context.application.enabled_languages) == 1:
            await update.message.reply_text(
                t(current_language).pgettext(
                    "bot-generic",
                    "Unfortunately, you can`t change the language — this bot supports only one.",
                )
            )
        else:
            await self.send_language_selector(update, context)
