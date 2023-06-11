from abc import ABC, abstractmethod
from typing import ClassVar

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
)

from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import BaseHandlerCallback


class SelectLanguageHandler(BaseHandlerCallback, ABC):
    STATE_LANGUAGE_SELECTION: ClassVar[int] = -11
    SKIP_LANGUAGE_SELECTION_IF_SINGLE: ClassVar[int] = True

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
                user_language, context, with_abort=True, language_friendly=False
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
    def get_select_language_handlers(cls) -> dict[int, list]:
        return {
            cls.STATE_LANGUAGE_SELECTION: [
                CallbackQueryHandler(
                    cls.partial(cls.handle_language_selected), r"^language:(\w+)$"
                ),
            ],
        }
