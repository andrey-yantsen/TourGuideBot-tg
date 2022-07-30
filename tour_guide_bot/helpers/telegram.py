from functools import partial
from babel import Locale
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from tour_guide_bot.models.telegram import TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
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


class BaseHandlerCallback:
    def __init__(self, db_session):
        self.db_session = db_session
        self.user = None

    @classmethod
    def get_handlers(cls):
        raise NotImplementedError()

    @classmethod
    async def build_and_run(cls, callback, update: Update, context: ContextTypes.DEFAULT_TYPE):
        async with AsyncSession(context.application.db_engine, expire_on_commit=False) as session:
            handler = cls(session)
            return await callback(handler, update, context)

    @classmethod
    def partial(cls, callback):
        return partial(cls.build_and_run, callback)

    @staticmethod
    def is_admin_app(context: ContextTypes.DEFAULT_TYPE) -> bool:
        return context.application.__class__.__name__ == 'AdminBot'

    async def get_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
        user = await self.get_user(update, context)

        if self.is_admin_app(context):
            return user.admin_language
        else:
            return user.guest_language

    async def get_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> TelegramUser:
        if self.user:
            return self.user

        stmt = select(TelegramUser).where(TelegramUser.id == update.effective_user.id).options(
            selectinload(TelegramUser.admin), selectinload(TelegramUser.guest))
        user = await self.db_session.scalar(stmt)

        if not user:
            user = TelegramUser(id=update.effective_user.id)

            if update.effective_user.language_code in context.application.enabled_languages:
                user.language = update.effective_user.language_code
            else:
                user.language = context.application.default_language

            self.db_session.add(user)
            await self.db_session.commit()

        self.user = user

        return self.user

    def get_language_select_inline_keyboard(self, current_language: str, context: ContextTypes.DEFAULT_TYPE, callback_data_prefix: str = 'language:'):
        keyboard = [[]]

        for locale_name in context.application.enabled_languages:
            if len(keyboard[len(keyboard) - 1]) == 1:
                keyboard.append([])

            locale = Locale.parse(locale_name)

            if locale_name != current_language:
                locale_text = "%s (%s)" % (locale.get_language_name(current_language),
                                           locale.get_language_name(locale_name))
            else:
                locale_text = locale.get_language_name(locale_name)

            keyboard[len(keyboard) - 1].append(
                InlineKeyboardButton(locale_text.title(), callback_data="%s%s" % (callback_data_prefix, locale_name))
            )

        return InlineKeyboardMarkup(inline_keyboard=keyboard)
