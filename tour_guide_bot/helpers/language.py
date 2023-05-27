from babel import Locale
from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import BaseHandlerCallback


class LanguageHandler(BaseHandlerCallback):
    @classmethod
    def get_handlers(cls) -> list:
        return [
            CommandHandler("language", cls.partial(cls.start)),
            CallbackQueryHandler(
                cls.partial(cls.set_language), "^change_user_language:(.*)$"
            ),
        ]

    async def set_language(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        required_language = context.matches[0].group(1)
        current_language = await self.get_language(update, context)

        if required_language in context.application.enabled_languages:
            user = await self.get_user(update, context)
            user.language = required_language
            self.db_session.add(user)
            await self.db_session.commit()

            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                t(required_language)
                .pgettext("any-bot", "The language has been changed to {0}.")
                .format(
                    Locale.parse(required_language).get_language_name(required_language)
                )
            )
        else:
            await update.callback_query.answer(
                t(current_language).pgettext(
                    "any-bot", "Something went wrong, please try again."
                )
            )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        current_language = await self.get_language(update, context)

        if len(context.application.enabled_languages) == 1:
            await update.message.reply_text(
                t(current_language).pgettext(
                    "any-bot",
                    "Unfortunately, you can`t change the language — this bot supports only one.",
                )
            )
        else:
            await update.message.reply_text(
                t(current_language).pgettext(
                    "any-bot", "Please select the language you prefer"
                ),
                reply_markup=self.get_language_select_inline_keyboard(
                    current_language, context, "change_user_language:"
                ),
            )
