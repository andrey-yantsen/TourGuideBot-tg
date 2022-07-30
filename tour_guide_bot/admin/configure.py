from typing import Optional
from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from tour_guide_bot import t
from tour_guide_bot.helpers import language
from tour_guide_bot.helpers.telegram import BaseHandlerCallback
from tour_guide_bot.models.settings import Settings, SettingsKey


class ConfigureCommandHandler(BaseHandlerCallback):
    STATE_INIT = 1
    STATE_WELCOME_MESSAGE_LANGUAGE = 2
    STATE_WELCOME_MESSAGE = 3

    @classmethod
    def get_handlers(cls):
        return [
            ConversationHandler(
                entry_points=[CommandHandler('configure', cls.partial(cls.start))],
                states={
                    cls.STATE_INIT: [
                        CallbackQueryHandler(cls.partial(cls.change_welcome_message_init), '^change_welcome_message$'),
                    ],
                    cls.STATE_WELCOME_MESSAGE_LANGUAGE: [
                        CallbackQueryHandler(cls.partial(cls.change_welcome_message), '^change_welcome_message:(.*)$'),
                    ],
                    cls.STATE_WELCOME_MESSAGE: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, cls.partial(cls.change_welcome_message_text)),
                        MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.TEXT,
                                       cls.partial(cls.incorrect_welcome_message)),
                    ],
                },
                fallbacks=[
                    CommandHandler('cancel', cls.partial(cls.cancel)),
                    CallbackQueryHandler(cls.partial(cls.cancel), 'cancel'),
                ],
                name='admin-configure',
                persistent=True
            )
        ]

    async def change_welcome_message_init(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if len(context.application.enabled_languages) == 1:
            return self.change_welcome_message(update, context, context.application.default_language)

        user = await self.get_user(update, context)

        language_keyboard = self.get_language_select_inline_keyboard(
            user.admin_language, context, 'change_welcome_message:')
        language_keyboard.inline_keyboard += [[
            InlineKeyboardButton(t(user.admin_language).pgettext(
                'bot-generic', 'Abort'), callback_data='cancel')
        ]]

        await update.callback_query.edit_message_text(t(user.admin_language).pgettext(
            'admin-configure', 'Please select the language for the welcome-message you want to edit.'),
            reply_markup=language_keyboard)

        return self.STATE_WELCOME_MESSAGE_LANGUAGE

    async def change_welcome_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, force_language: Optional[str] = None):
        target_language = force_language if force_language else context.matches[0].group(1)
        context.user_data['welcome_message_target_language'] = target_language

        user = await self.get_user(update, context)

        if target_language not in context.application.enabled_languages:
            del context.user_data['welcome_message_target_language']
            await update.callback_query.edit_message_text(t(user.admin_language).pgettext(
                'admin-configure', 'Something went wrong; please try again.'))
            return ConversationHandler.END

        stmt = select(Settings).where((Settings.key == SettingsKey.guide_welcome_message)
                                      & (Settings.language == target_language))
        welcome_message = await self.db_session.scalar(stmt)

        if welcome_message:
            await update.callback_query.edit_message_text(t(user.admin_language).pgettext(
                'admin-configure', 'The bot currently have the following welcome message. Please send me a new one if you want to change it, or send /cancel to abort the modification.'))

            await context.application.bot.send_message(update.effective_chat.id, welcome_message.value, disable_web_page_preview=True, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await update.callback_query.edit_message_text(t(user.admin_language).pgettext(
                'admin-configure', "The bot currently doesn't have a welcome message. Please send me one."))

        return self.STATE_WELCOME_MESSAGE

    async def incorrect_welcome_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)
        await update.callback_query.edit_message_text(t(user.admin_language).pgettext(
            'admin-configure', "You can use only text as bot's welcome message."))
        return self.STATE_WELCOME_MESSAGE

    async def change_welcome_message_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        target_language = context.user_data.get('welcome_message_target_language')
        user = await self.get_user(update, context)

        if not target_language:
            await update.callback_query.edit_message_text(t(user.admin_language).pgettext(
                'admin-configure', 'Something went wrong; please try again.'))
            return ConversationHandler.END

        stmt = select(Settings).where((Settings.key == SettingsKey.guide_welcome_message)
                                      & (Settings.language == target_language))
        welcome_message = await self.db_session.scalar(stmt)

        if not welcome_message:
            welcome_message = Settings(key=SettingsKey.guide_welcome_message, language=target_language)

        welcome_message.value = update.message.text_markdown_v2_urled

        self.db_session.add(welcome_message)
        await self.db_session.commit()
        del context.user_data['welcome_message_target_language']

        await update.message.reply_text(t(user.admin_language).pgettext('admin-configure', "Bot's welcome message has been changed."))

        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        if update.message:
            await update.message.reply_text(t(user.admin_language).pgettext(
                'bot-generic', 'Cancelled.'),
                reply_markup=ReplyKeyboardRemove())
        elif update.callback_query:
            await update.callback_query.edit_message_text(t(user.admin_language).pgettext('bot-generic', 'Cancelled.'))

        return ConversationHandler.END

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        await update.message.reply_text(t(user.admin_language).pgettext(
            'admin-configure', 'Please select the parameter you want to change.'),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(t(user.admin_language).pgettext('admin-bot-configure',
                                                                         'Guide welcome message'), callback_data='change_welcome_message')
                ],
                [
                    InlineKeyboardButton(t(user.admin_language).pgettext(
                        'bot-generic', 'Abort'), callback_data='cancel')
                ],
            ]))

        return self.STATE_INIT
