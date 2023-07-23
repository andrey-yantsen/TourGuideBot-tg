from abc import ABC, abstractmethod
from typing import ClassVar, Optional, Sequence

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
    STATE_SELECT_TOUR: ClassVar[Optional[int]] = -10

    SKIP_TOUR_SELECTION_IF_SINGLE: ClassVar[int] = False

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

    async def get_acceptable_tours(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> Sequence[Tour]:
        return (
            await self.db_session.scalars(
                select(Tour).options(selectinload(Tour.translations))
            )
        ).all()

    async def handle_no_tours_found(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)
        await self.edit_or_reply_text(
            update, context, t(language).pgettext("bot-generic", "No tours found.")
        )
        return ConversationHandler.END

    async def send_tour_selector(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        tours: Sequence[Tour] = await self.get_acceptable_tours(update, context)

        if len(tours) == 1 and self.SKIP_TOUR_SELECTION_IF_SINGLE:
            if update.callback_query:
                await update.callback_query.answer()

            return await self.after_tour_selected(tours[0], update, context, True)

        language = await self.get_language(update, context)

        if len(tours) == 0:
            if update.callback_query:
                await update.callback_query.answer()

            return await self.handle_no_tours_found(update, context)

        keyboard = []

        for tour in tours:
            title = get_tour_title(tour, language, context)
            keyboard.append(
                [
                    InlineKeyboardButton(
                        title,
                        callback_data=self.get_callback_data("select_tour", tour.id),
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    t(language).pgettext("bot-generic", "Abort"),
                    callback_data=self.get_callback_data("cancel_tour_selection"),
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

        return self.STATE_SELECT_TOUR

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
    def get_select_tour_handlers(cls) -> list:
        return [
            CallbackQueryHandler(
                cls.partial(cls.handle_selected_tour),
                cls.get_callback_data_pattern("select_tour", r"(\d+)"),
            ),
            CallbackQueryHandler(
                cls.partial(
                    cls.cancel
                    if cls.STATE_SELECT_TOUR
                    else cls.cancel_without_conversation
                ),
                cls.get_callback_data_pattern("cancel_tour_selection"),
            ),
        ]
