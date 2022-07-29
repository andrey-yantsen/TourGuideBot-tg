from babel import Locale
from .telegram import BaseHandler
from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from tour_guide_bot import t
from tour_guide_bot.models.admin import Admin, AdminPermissions
from . import log


class LanguageHandler(BaseHandler):
    @classmethod
    def get_handlers(cls, app, db):
        return [
            CommandHandler('language', cls.partial(app, db, 'start')),
            CallbackQueryHandler(cls.partial(app, db, 'set_language'), '^change_language:'),
        ]

    async def set_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        log.debug('Got set_language callback: %s' % (update, ))

        data = update.callback_query.data.split(':')

        current_language = await self.get_language(update)

        if len(data) == 2 and data[1] in self.app.enabled_languages:
            user = await self.get_user(update)

            if self.is_admin_app:
                user.admin.language = data[1]
                self.db_session.add(user.admin)
            else:
                user.guest.language = data[1]
                self.db_session.add(user.guest)
            await self.db_session.commit()

            await update.callback_query.answer('')
            await update.callback_query.edit_message_text(t(data[1]).pgettext('any-bot', 'The language has been changed to %s.') % (Locale.parse(data[1]).get_language_name(data[1]), ))
        else:
            await update.callback_query.answer(t(current_language).pgettext('any-bot', 'Something went wrong, please try again.'))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        log.debug('Got language command: %s' % (update, ))

        current_language = await self.get_language(update)

        if len(self.app.enabled_languages) == 1:
            await update.message.reply_text(t(current_language).pgettext(
                'any-bot', 'Unfortunately, you can`t change the language — this bot supports only one.'))
        else:
            keyboard = [[]]

            for locale_name in self.app.enabled_languages:
                if len(keyboard[len(keyboard) - 1]) == 1:
                    keyboard.append([])

                locale = Locale.parse(locale_name)

                if locale_name != current_language:
                    locale_text = "%s (%s)" % (locale.get_language_name(current_language),
                                               locale.get_language_name(locale_name))
                else:
                    locale_text = locale.get_language_name(locale_name)

                keyboard[len(keyboard) - 1].append(
                    InlineKeyboardButton(locale_text.title(), callback_data="change_language:%s" % locale_name)
                )

            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await update.message.reply_text(t(current_language).pgettext(
                'any-bot', 'Please select the language you prefer'), reply_markup=reply_markup)
