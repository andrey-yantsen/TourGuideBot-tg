import abc
from binascii import crc32
from functools import partial
from inspect import isawaitable

from babel import Locale
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import (
    BaseHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
)

from tour_guide_bot import t
from tour_guide_bot.models import log
from tour_guide_bot.models.guide import Tour
from tour_guide_bot.models.telegram import TelegramUser


class BaseHandlerCallback:
    __metaclass__ = abc.ABCMeta

    def __init__(self, db_session: AsyncSession):
        self.db_session: AsyncSession = db_session
        self.user: TelegramUser | None = None

    @classmethod
    @abc.abstractmethod
    def get_handlers(cls) -> list[BaseHandler]:
        pass

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        if hasattr(self, "cleanup_context"):
            cleanup_result = self.cleanup_context(context)

            if isawaitable(cleanup_result):
                await cleanup_result

        if update.callback_query:
            await update.callback_query.answer()

        await self.edit_or_reply_text(
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
    ) -> Message:
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
    def partial(cls, callback) -> callable:
        return partial(cls.build_and_run, callback)

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
        user: TelegramUser | None = await self.db_session.scalar(stmt)

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

    async def get_languages(
        self,
        current_language: str,
        context: ContextTypes.DEFAULT_TYPE,
        language_friendly: bool = True,
    ):
        ret = []
        for locale_name in context.application.enabled_languages:
            locale = Locale.parse(locale_name)

            if locale_name != current_language and language_friendly:
                locale_text = "%s (%s)" % (
                    locale.get_language_name(current_language),
                    locale.get_language_name(locale_name),
                )
            else:
                locale_text = locale.get_language_name(locale_name)

            ret.append((locale_name, locale_text))

        return ret

    async def get_language_select_inline_keyboard(
        self,
        current_language: str,
        context: ContextTypes.DEFAULT_TYPE,
        callback_data_prefix: str = "language:",
        with_abort: bool = False,
        language_friendly: bool = True,
    ) -> InlineKeyboardMarkup:
        keyboard = []

        for locale_name, locale_text in await self.get_languages(
            current_language, context, language_friendly
        ):
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

    @classmethod
    def get_callback_data(cls, *args) -> str:
        ret = str(crc32((cls.__module__ + "." + cls.__name__).encode("ascii")))

        if args:
            ret += ":" + ":".join([str(a) for a in args])

        return ret

    @classmethod
    def get_callback_data_pattern(cls, *args) -> str:
        return f"^{cls.get_callback_data(*args)}$"


class AdminProtectedBaseHandlerCallback(BaseHandlerCallback):
    @classmethod
    async def build_and_run(
        cls: BaseHandlerCallback,
        callback,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
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


class SubcommandHandler(AdminProtectedBaseHandlerCallback):
    __metaclass__ = abc.ABCMeta

    @staticmethod
    @abc.abstractmethod
    def get_name(language: str) -> str:
        pass

    @classmethod
    async def is_available(cls, db_session: AsyncSession) -> bool:
        return True


class MenuCommandHandler(AdminProtectedBaseHandlerCallback):
    __metaclass__ = abc.ABCMeta

    MENU_ITEMS: list[type[SubcommandHandler]] = []

    @classmethod
    @abc.abstractmethod
    def get_main_handlers(cls) -> list[BaseHandler]:
        pass

    @abc.abstractmethod
    def get_main_menu_text(self, language: str) -> str:
        pass

    @abc.abstractmethod
    def get_main_menu_unavailable_text(self, language: str) -> str:
        pass

    async def handle_menu_unavailable(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        msg = self.get_main_menu_unavailable_text(
            await self.get_language(update, context)
        )

        keyboard = await self.get_extra_buttons(update, context)

        await self.edit_or_reply_text(
            update,
            context,
            msg,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        )

    async def handle_menu_available(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        keyboard = await self.get_menu(update, context) + await self.get_extra_buttons(
            update, context
        )
        await self.edit_or_reply_text(
            update,
            context,
            self.get_main_menu_text(await self.get_language(update, context)),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        )

    async def is_menu_available(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        return True

    @classmethod
    def get_submenu_handlers(cls) -> list[BaseHandler]:
        ret = []

        for item in cls.MENU_ITEMS:
            ret += item.get_handlers()

        return ret

    @classmethod
    def get_handlers(cls):
        ret = cls.get_main_handlers()
        ret += cls.get_submenu_handlers()
        ret.append(
            CallbackQueryHandler(
                cls.partial(cls.cancel_without_conversation),
                cls.get_callback_data_pattern("cancel"),
            )
        )

        return ret

    async def cancel_without_conversation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        # Skipping returning ConversationHandler.END to prevent finishing the current
        # conversation
        await super().cancel(update, context)

    async def get_extra_buttons(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> list[list[InlineKeyboardButton]]:
        return [
            [
                InlineKeyboardButton(
                    t(await self.get_language(update, context)).pgettext(
                        "bot-generic", "Abort"
                    ),
                    callback_data=self.get_callback_data("cancel"),
                )
            ],
        ]

    async def get_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> list[list[InlineKeyboardButton]]:
        keyboard = []

        for item in self.MENU_ITEMS:
            if not await item.is_available(self.db_session):
                continue

            keyboard.append(
                [
                    InlineKeyboardButton(
                        item.get_name(await self.get_language(update, context)),
                        callback_data=item.get_callback_data(),
                    )
                ]
            )

        return keyboard

    async def main_entrypoint(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.callback_query:
            await update.callback_query.answer()

        if await self.is_menu_available(update, context):
            return await self.handle_menu_available(update, context)

        return await self.handle_menu_unavailable(update, context)


def get_tour_title(
    tour: Tour, current_language: str, context: ContextTypes.DEFAULT_TYPE
) -> str:
    default_language = context.application.default_language

    if len(tour.translations) == 0:
        title = "Unnamed tour #%d" % tour.id
        log.warning(
            t()
            .pgettext("bot-generic", "Tour #{0} doesn't have any translations.")
            .format(tour.id)
        )
    else:
        translations = {
            translation.language: translation for translation in tour.translations
        }

        if current_language in translations:
            title = translations[current_language].title
        elif default_language in translations:
            title = translations[default_language].title
        else:
            log.warning(
                t()
                .pgettext(
                    "bot-generic",
                    "Tour #{0} doesn't have a translation for the default language ({1}).",
                )
                .format(tour.id, default_language)
            )
            title = translations[0].title

    return title
