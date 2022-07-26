from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
from tour_guide_bot.helpers.telegram import AdminProtectedBaseHandlerCallback
from tour_guide_bot.models.settings import Settings, SettingsKey


class ConfigureCommandHandler(AdminProtectedBaseHandlerCallback):
    STATE_INIT = 1
    STATE_WELCOME_MESSAGE_LANGUAGE = 2
    STATE_WELCOME_MESSAGE = 3
    STATE_AUDIO_TO_VOICE = 4
    STATE_DELAY_BETWEEN_MESSAGES = 5

    @classmethod
    def get_handlers(cls):
        return [
            ConversationHandler(
                entry_points=[CommandHandler("configure", cls.partial(cls.start))],
                states={
                    cls.STATE_INIT: [
                        CallbackQueryHandler(
                            cls.partial(cls.change_welcome_message_init),
                            "^change_welcome_message$",
                        ),
                        CallbackQueryHandler(
                            cls.partial(cls.change_audio_to_voice_init),
                            "^audio_to_voice$",
                        ),
                        CallbackQueryHandler(
                            cls.partial(cls.change_delay_between_messages_init),
                            "^delay_between_messages$",
                        ),
                    ],
                    cls.STATE_WELCOME_MESSAGE_LANGUAGE: [
                        CallbackQueryHandler(
                            cls.partial(cls.change_welcome_message),
                            "^change_welcome_message:(.*)$",
                        ),
                    ],
                    cls.STATE_AUDIO_TO_VOICE: [
                        CallbackQueryHandler(
                            cls.partial(cls.change_audio_to_voice),
                            "^audio_to_voice:(enable|disable)$",
                        ),
                    ],
                    cls.STATE_DELAY_BETWEEN_MESSAGES: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.change_delay_between_messages),
                        ),
                    ],
                    cls.STATE_WELCOME_MESSAGE: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.change_welcome_message_text),
                        ),
                        MessageHandler(
                            filters.ALL & ~filters.COMMAND & ~filters.TEXT,
                            cls.partial(cls.incorrect_welcome_message),
                        ),
                    ],
                },
                fallbacks=[
                    CommandHandler("cancel", cls.partial(cls.cancel)),
                    CallbackQueryHandler(cls.partial(cls.cancel), "cancel"),
                ],
                name="admin-configure",
                persistent=True,
            )
        ]

    async def change_delay_between_messages_init(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)
        delay_between_messages_state = await Settings.load(
            self.db_session, SettingsKey.delay_between_messages
        )

        await update.callback_query.edit_message_text(
            t(language).pgettext(
                "admin-configure",
                "Current delay between messages is %0.1fs. "
                "Please enter a desired delay (float value between 0 and 4.5).",
            )
            % (float(delay_between_messages_state.value)),
        )

        return self.STATE_DELAY_BETWEEN_MESSAGES

    async def change_delay_between_messages(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)

        try:
            delay = float(update.message.text)
        except ValueError:
            await update.message.reply_text(
                t(language).pgettext(
                    "admin-configure",
                    "Please enter a float value between 0 and 4.5.",
                )
            )
            return

        if not 0 <= delay <= 4.5:
            await update.message.reply_text(
                t(language).pgettext(
                    "admin-configure",
                    "Please enter a float value between 0 and 4.5.",
                )
            )
            return

        delay_between_messages_state = await Settings.load(
            self.db_session, SettingsKey.delay_between_messages
        )
        delay_between_messages_state.value = delay
        self.db_session.add(delay_between_messages_state)
        await self.db_session.commit()

        await update.message.reply_text(
            t(language).pgettext(
                "admin-configure",
                "The delay was updated!",
            )
        )

        return ConversationHandler.END

    async def change_audio_to_voice_init(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)
        audio_to_voice_state = await Settings.load(
            self.db_session, SettingsKey.audio_to_voice
        )

        if audio_to_voice_state.is_enabled:
            await update.callback_query.edit_message_text(
                t(language).pgettext(
                    "admin-configure",
                    "Audio\-to\-voice conversion suggestions are currently *enabled*\. Would you like to disable them?",
                ),
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                t(language).pgettext("bot-generic", "Yes"),
                                callback_data="audio_to_voice:disable",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                t(language).pgettext("bot-generic", "Abort"),
                                callback_data="cancel",
                            )
                        ],
                    ]
                ),
            )
        else:
            await update.callback_query.edit_message_text(
                t(language).pgettext(
                    "admin-configure",
                    "Audio\-to\-voice conversion suggestions are currently *disabled*\. Would you like to enable them?",
                ),
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                t(language).pgettext("bot-generic", "Yes"),
                                callback_data="audio_to_voice:enable",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                t(language).pgettext("bot-generic", "Abort"),
                                callback_data="cancel",
                            )
                        ],
                    ]
                ),
            )

        return self.STATE_AUDIO_TO_VOICE

    async def change_audio_to_voice(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)
        audio_to_voice_state = await Settings.load(
            self.db_session, SettingsKey.audio_to_voice
        )
        if context.matches[0].group(1) == "enable":
            audio_to_voice_state.enable()
        else:
            audio_to_voice_state.disable()

        self.db_session.add(audio_to_voice_state)
        await self.db_session.commit()

        if context.matches[0].group(1) == "enable":
            await update.callback_query.edit_message_text(
                t(language).pgettext(
                    "admin-configure",
                    "Audio-to-voice conversion suggestions were enabled.",
                )
            )
        else:
            await update.callback_query.edit_message_text(
                t(language).pgettext(
                    "admin-configure",
                    "Audio-to-voice conversion suggestions were disabled.",
                )
            )

        return ConversationHandler.END

    async def change_welcome_message_init(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if len(context.application.enabled_languages) == 1:
            return await self.change_welcome_message(
                update, context, context.application.default_language
            )

        user = await self.get_user(update, context)

        await update.callback_query.edit_message_text(
            t(user.language).pgettext(
                "admin-configure",
                "Please select the language for the welcome message you want to edit.",
            ),
            reply_markup=self.get_language_select_inline_keyboard(
                user.language, context, "change_welcome_message:", True
            ),
        )

        return self.STATE_WELCOME_MESSAGE_LANGUAGE

    async def change_welcome_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        force_language: str | None = None,
    ):
        target_language = (
            force_language if force_language else context.matches[0].group(1)
        )
        context.user_data["welcome_message_target_language"] = target_language

        user = await self.get_user(update, context)

        if target_language not in context.application.enabled_languages:
            del context.user_data["welcome_message_target_language"]
            await update.callback_query.edit_message_text(
                t(user.language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                )
            )
            return ConversationHandler.END

        stmt = select(Settings).where(
            (Settings.key == SettingsKey.guide_welcome_message)
            & (Settings.language == target_language)
        )
        welcome_message = await self.db_session.scalar(stmt)

        if welcome_message:
            await update.callback_query.edit_message_text(
                t(user.language).pgettext(
                    "admin-configure",
                    "The bot currently has the following welcome message. Please send me a new one if you want to change it, or send /cancel to abort the modification.",
                )
            )

            await context.application.bot.send_message(
                update.effective_chat.id,
                welcome_message.value,
                disable_web_page_preview=True,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        else:
            await update.callback_query.edit_message_text(
                t(user.language).pgettext(
                    "admin-configure",
                    "The bot currently doesn't have a welcome message. Please send me one.",
                )
            )

        return self.STATE_WELCOME_MESSAGE

    async def incorrect_welcome_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        user = await self.get_user(update, context)
        await update.callback_query.edit_message_text(
            t(user.language).pgettext(
                "admin-configure", "You can use only text as the bot's welcome message."
            )
        )
        return self.STATE_WELCOME_MESSAGE

    async def change_welcome_message_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        target_language = context.user_data.get("welcome_message_target_language")
        user = await self.get_user(update, context)

        if not target_language:
            await update.callback_query.edit_message_text(
                t(user.language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                )
            )
            return ConversationHandler.END

        stmt = select(Settings).where(
            (Settings.key == SettingsKey.guide_welcome_message)
            & (Settings.language == target_language)
        )
        welcome_message = await self.db_session.scalar(stmt)

        if not welcome_message:
            welcome_message = Settings(
                key=SettingsKey.guide_welcome_message, language=target_language
            )

        welcome_message.value = update.message.text_markdown_v2_urled

        self.db_session.add(welcome_message)
        await self.db_session.commit()
        del context.user_data["welcome_message_target_language"]

        await update.message.reply_text(
            t(user.language).pgettext(
                "admin-configure", "Bot's welcome message has been changed."
            )
        )

        return ConversationHandler.END

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        await update.message.reply_text(
            t(user.language).pgettext(
                "admin-configure", "Please select the parameter you want to change."
            ),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            t(user.language).pgettext(
                                "admin-bot-configure", "Guide welcome message"
                            ),
                            callback_data="change_welcome_message",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            t(user.language).pgettext(
                                "admin-bot-configure", "Audio-to-voice suggestions"
                            ),
                            callback_data="audio_to_voice",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            t(user.language).pgettext(
                                "admin-bot-configure", "Delay between messages"
                            ),
                            callback_data="delay_between_messages",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            t(user.language).pgettext("bot-generic", "Abort"),
                            callback_data="cancel",
                        )
                    ],
                ]
            ),
        )

        return self.STATE_INIT
