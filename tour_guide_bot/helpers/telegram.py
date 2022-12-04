from functools import partial

from babel import Locale
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from tour_guide_bot import t
from tour_guide_bot.models.guide import Tour
from tour_guide_bot.models.telegram import TelegramUser

from . import log


class BaseHandlerCallback:
    def __init__(self, db_session):
        self.db_session = db_session
        self.user = None

    @classmethod
    def get_handlers(cls):
        raise NotImplementedError()

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        if hasattr(self, "cleanup_context"):
            self.cleanup_context(context)

        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.delete_message()

        await self.reply_text(
            update, context, t(user.language).pgettext("bot-generic", "Cancelled.")
        )
        return ConversationHandler.END

    @staticmethod
    async def edit_or_reply_text(
        update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, **kwargs
    ):
        if update.callback_query:
            return await update.callback_query.edit_message_text(text, **kwargs)
        else:
            return await BaseHandlerCallback.reply_text(update, context, text, **kwargs)

    @staticmethod
    async def reply_text(
        update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, **kwargs
    ):
        async def _reply(*args, **kwargs):
            return await context.application.bot.send_message(
                update.effective_chat.id, *args, **kwargs
            )

        if update.message:
            reply = update.message.reply_text
        else:
            reply = _reply

        return await reply(text, **kwargs)

    async def unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        language = await self.get_language(update, context)
        await update.message.reply_text(
            t(language).pgettext("bot-generic", "Unknown command.")
        )

    @classmethod
    async def build_and_run(
        cls, callback, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        async with AsyncSession(
            context.application.db_engine, expire_on_commit=False
        ) as session:
            handler = cls(session)
            return await callback(handler, update, context)

    @classmethod
    def partial(cls, callback):
        return partial(cls.build_and_run, callback)

    @staticmethod
    def is_admin_app(context: ContextTypes.DEFAULT_TYPE) -> bool:
        return context.application.__class__.__name__ == "AdminBot"

    async def get_language(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> str:
        return (await self.get_user(update, context)).language

    async def get_user(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> TelegramUser:
        if self.user:
            return self.user

        stmt = (
            select(TelegramUser)
            .where(TelegramUser.id == update.effective_user.id)
            .options(selectinload(TelegramUser.admin), selectinload(TelegramUser.guest))
        )
        user = await self.db_session.scalar(stmt)

        if not user:
            user = TelegramUser(id=update.effective_user.id)

            if (
                update.effective_user.language_code
                in context.application.enabled_languages
            ):
                user.language = update.effective_user.language_code
            else:
                user.language = context.application.default_language

            self.db_session.add(user)
            await self.db_session.commit()

        self.user = user

        return self.user

    def get_language_select_inline_keyboard(
        self,
        current_language: str,
        context: ContextTypes.DEFAULT_TYPE,
        callback_data_prefix: str = "language:",
        with_abort: bool = False,
    ):
        keyboard = []

        for locale_name in context.application.enabled_languages:
            locale = Locale.parse(locale_name)

            if locale_name != current_language:
                locale_text = "%s (%s)" % (
                    locale.get_language_name(current_language),
                    locale.get_language_name(locale_name),
                )
            else:
                locale_text = locale.get_language_name(locale_name)

            keyboard.append(
                [
                    InlineKeyboardButton(
                        locale_text.title(),
                        callback_data="%s%s" % (callback_data_prefix, locale_name),
                    )
                ]
            )

        if with_abort:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        t(current_language).pgettext("bot-generic", "Abort"),
                        callback_data="cancel",
                    )
                ]
            )

        return InlineKeyboardMarkup(inline_keyboard=keyboard)


class AdminProtectedBaseHandlerCallback(BaseHandlerCallback):
    @classmethod
    async def build_and_run(
        cls, callback, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        async with AsyncSession(
            context.application.db_engine, expire_on_commit=False
        ) as session:
            handler = cls(session)

            user = await handler.get_user(update, context)

            if not user.admin:
                await cls.edit_or_reply_text(
                    update,
                    context,
                    t(user.language).pgettext("admin-bot", "Access denied."),
                )
                return ConversationHandler.END

            return await callback(handler, update, context)


def get_tour_title(
    tour: Tour, current_language: str, context: ContextTypes.DEFAULT_TYPE
) -> str:
    default_language = context.application.default_language

    if len(tour.translation) == 0:
        title = "Unnamed tour #%d" % tour.id
        log.warning(
            t().pgettext(
                "bot-generic",
                "Tour #{0} doesn't have any translations.".format(tour.id),
            )
        )
    elif len(tour.translation) == 1:
        title = tour.translation[0].title

        if tour.translation[0].language != default_language:
            log.error(
                t().pgettext(
                    "bot-generic",
                    "Tour #{0} doesn't have a translation for the default language ({1}).".format(
                        tour.id, default_language
                    ),
                )
            )
    else:
        translations = {
            translation.language: translation for translation in tour.translation
        }

        if current_language in translations:
            title = translations[current_language].title
        elif default_language in translations:
            title = translations[default_language].title
        else:
            log.warning(
                t().pgettext(
                    "bot-generic",
                    "Tour #{0} doesn't have a translation for the default language ({1}).".format(
                        tour.id, default_language
                    ),
                )
            )
            title = translations[0].title

    return title
