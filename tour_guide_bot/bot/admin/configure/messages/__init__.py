import abc

from sqlalchemy import select
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tour_guide_bot import t
from tour_guide_bot.helpers.language_selector import SelectLanguageHandler
from tour_guide_bot.helpers.telegram import SubcommandHandler
from tour_guide_bot.models.settings import Settings, SettingsKey


class MessagesBase(SubcommandHandler, SelectLanguageHandler):
    STATE_CHANGE_MESSAGE = 1

    @staticmethod
    @abc.abstractmethod
    def get_message_name(language: str) -> str:
        pass

    @staticmethod
    @abc.abstractmethod
    def get_message_settings_key() -> SettingsKey:
        pass

    @classmethod
    def get_handlers(cls):
        return [
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        cls.partial(cls.send_language_selector),
                        cls.get_callback_data_pattern(),
                    )
                ],
                states={
                    cls.STATE_LANGUAGE_SELECTION: cls.get_select_language_handlers(),
                    cls.STATE_CHANGE_MESSAGE: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.change_message_text),
                        ),
                        MessageHandler(
                            filters.ALL & ~filters.COMMAND & ~filters.TEXT,
                            cls.partial(cls.incorrect_message),
                        ),
                    ],
                },
                fallbacks=[
                    CommandHandler("cancel", cls.partial(cls.cancel)),
                    CallbackQueryHandler(cls.partial(cls.cancel), "cancel"),
                    MessageHandler(filters.COMMAND, cls.partial(cls.unknown_command)),
                    MessageHandler(filters.ALL, cls.partial(cls.unexpected_message)),
                ],
                name="admin-configure-" + cls.__module__ + "." + cls.__name__.lower(),
                persistent=True,
            )
        ]

    def get_language_selection_message(self, user_language: str) -> str:
        return t(user_language).pgettext(
            "admin-configure",
            "Please select the language for the {} you want to edit.".format(
                self.get_message_name(user_language)
            ),
        )

    async def after_language_selected(
        self,
        language: str,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_language: bool,
    ):
        context.user_data["message_target_language"] = language

        user = await self.get_user(update, context)

        stmt = select(Settings).where(
            (Settings.key == self.get_message_settings_key())
            & (Settings.language == language)
        )
        message: Settings | None = await self.db_session.scalar(stmt)

        await update.callback_query.answer()
        if message:
            await update.callback_query.edit_message_text(
                t(user.language).pgettext(
                    "admin-configure",
                    "The bot currently has the following {}. Please send me a new one if you want to change it, "
                    "or send /cancel to abort the modification.".format(
                        self.get_message_name(user.language)
                    ),
                )
            )

            await context.application.bot.send_message(
                update.effective_chat.id,
                message.value,
                disable_web_page_preview=True,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        else:
            await update.callback_query.edit_message_text(
                t(user.language).pgettext(
                    "admin-configure",
                    "The bot currently doesn't have a {}. Please send me one.".format(
                        self.get_message_name(user.language)
                    ),
                )
            )

        return self.STATE_CHANGE_MESSAGE

    async def incorrect_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        user = await self.get_user(update, context)
        await update.callback_query.edit_message_text(
            t(user.language).pgettext(
                "admin-configure", "Please send me a regular text message."
            )
        )
        return self.STATE_CHANGE_MESSAGE

    async def change_message_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        target_language = context.user_data.get("message_target_language")
        user = await self.get_user(update, context)

        if not target_language:
            await update.callback_query.edit_message_text(
                t(user.language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                )
            )
            return ConversationHandler.END

        message = await Settings.load(
            self.db_session,
            self.get_message_settings_key(),
            target_language,
            create=True,
        )
        message.value = update.message.text_markdown_v2_urled

        self.db_session.add(message)
        await self.db_session.commit()

        await update.message.reply_text(
            t(user.language).pgettext(
                "admin-configure",
                "Bot's {} has been changed.".format(
                    self.get_message_name(user.language)
                ),
            )
        )

        del context.user_data["message_target_language"]

        return ConversationHandler.END
