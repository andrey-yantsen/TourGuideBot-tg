from abc import ABC, abstractmethod
from typing import ClassVar

from babel import Locale
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
)

from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import BaseHandlerCallback


class SelectLanguageHandler(BaseHandlerCallback, ABC):
    STATE_LANGUAGE_SELECTION: ClassVar[int] = -11
    SKIP_LANGUAGE_SELECTION_IF_SINGLE: ClassVar[bool] = True
    LANGUAGE_SELECTION_LANGUAGE_FRIENDLY: ClassVar[bool] = False

    @abstractmethod
    async def after_language_selected(
        self,
        language: str,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_language: bool,
    ):
        pass

    @abstractmethod
    def get_language_selection_message(self, user_language: str) -> str:
        pass

    async def get_languages(
        self,
        current_language: str,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> list[tuple[str, str]]:
        ret = []
        for locale_name in context.application.enabled_languages:
            locale = Locale.parse(locale_name)

            if (
                locale_name != current_language
                and self.LANGUAGE_SELECTION_LANGUAGE_FRIENDLY
            ):
                locale_text = "%s (%s)" % (
                    locale.get_language_name(current_language),
                    locale.get_language_name(locale_name),
                )
            else:
                locale_text = locale.get_language_name(current_language)

            ret.append((locale_name, locale_text))

        return ret

    async def get_language_select_inline_keyboard(
        self,
        current_language: str,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> InlineKeyboardMarkup:
        keyboard = []

        for locale_name, locale_text in await self.get_languages(
            current_language, context
        ):
            keyboard.append(
                [
                    InlineKeyboardButton(
                        locale_text.title(),
                        callback_data=self.get_callback_data("language", locale_name),
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    t(current_language).pgettext("bot-generic", "Abort"),
                    callback_data=self.get_callback_data("cancel_language_selection"),
                )
            ]
        )

        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    async def send_language_selector(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        user_language = await self.get_language(update, context)

        if update.callback_query:
            await update.callback_query.answer()

        if (
            len(context.application.enabled_languages) == 1
            and self.SKIP_LANGUAGE_SELECTION_IF_SINGLE
        ):
            return await self.after_language_selected(
                context.application.default_language, update, context, True
            )

        await self.edit_or_reply_text(
            update,
            context,
            self.get_language_selection_message(user_language),
            reply_markup=await self.get_language_select_inline_keyboard(
                user_language,
                context,
            ),
        )
        return self.STATE_LANGUAGE_SELECTION

    async def handle_language_selected(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if update.callback_query:
            await update.callback_query.answer()

        lang = context.matches[0].group(1)

        if lang not in context.application.enabled_languages:
            await self.edit_or_reply_text(
                update,
                context,
                t(await self.get_language(update, context)).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )

            return ConversationHandler.END

        return await self.after_language_selected(
            context.matches[0].group(1), update, context, False
        )

    @classmethod
    def get_select_language_handlers(cls) -> list:
        return [
            CallbackQueryHandler(
                cls.partial(cls.handle_language_selected),
                cls.get_callback_data_pattern("language", r"(\w+)"),
            ),
            CallbackQueryHandler(
                cls.partial(cls.cancel),
                cls.get_callback_data_pattern("cancel_language_selection"),
            ),
        ]
