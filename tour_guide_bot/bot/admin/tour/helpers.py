from abc import ABC, abstractmethod
from typing import ClassVar, Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
)

from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import BaseHandlerCallback, get_tour_title
from tour_guide_bot.models.guide import Tour


class SelectTourHandler(BaseHandlerCallback, ABC):
    STATE_TOUR_SELECTION: ClassVar[int] = -10
    SKIP_TOUR_SELECTION_IF_SINGLE: ClassVar[int] = True

    @abstractmethod
    async def after_tour_selected(
        self,
        tour: Tour,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_tour: bool,
    ):
        pass

    @abstractmethod
    def get_tour_selection_message(self, language: str) -> str:
        pass

    async def get_acceptable_tours(self) -> Sequence[Tour]:
        return (
            await self.db_session.scalars(
                select(Tour).options(selectinload(Tour.translations))
            )
        ).all()

    async def send_tour_selector(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        tours: Sequence[Tour] = self.get_acceptable_tours()

        if len(tours) == 1 and self.SKIP_TOUR_SELECTION_IF_SINGLE:
            if update.callback_query:
                await update.callback_query.answer()

            return await self.after_tour_selected(tours[0], update, context, True)

        user = await self.get_user(update, context)
        language = user.language

        if len(tours) == 0:
            if update.callback_query:
                await update.callback_query.answer()

            await self.edit_or_reply_text(
                update, context, t(language).pgettext("bot-admin", "No tours found.")
            )
            return ConversationHandler.END

        keyboard = []

        for tour in tours:
            title = get_tour_title(tour, user.language, context)
            keyboard.append(
                [
                    InlineKeyboardButton(
                        title, callback_data="select_tour:%s" % (tour.id,)
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    t(language).pgettext("bot-generic", "Abort"),
                    callback_data="cancel",
                )
            ]
        )

        if update.callback_query:
            await update.callback_query.answer()

        await self.edit_or_reply_text(
            update,
            context,
            self.get_tour_selection_message(language),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return self.STATE_TOUR_SELECTION

    async def handle_selected_tour(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        tour: Tour | None = await self.db_session.scalar(
            select(Tour)
            .options(selectinload(Tour.translations))
            .where(Tour.id == int(context.matches[0].group(1)))
        )

        if update.callback_query:
            await update.callback_query.answer()

        if tour is None:
            await self.edit_or_reply_text(
                update,
                context,
                t(await self.get_language(update, context)).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )

            return ConversationHandler.END

        return await self.after_tour_selected(tour, update, context, False)

    @classmethod
    def get_select_tour_handlers(cls) -> dict[int, list]:
        return {
            cls.STATE_TOUR_SELECTION: [
                CallbackQueryHandler(
                    cls.partial(cls.handle_selected_tour), r"^select_tour:(\d+)$"
                ),
            ],
        }


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
