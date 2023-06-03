from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
)

from tour_guide_bot import t
from tour_guide_bot.bot.admin.tour.edit import section
from tour_guide_bot.bot.admin.tour.edit.add_translation import AddTranslationHandler
from tour_guide_bot.bot.admin.tour.edit.rename import RenameHandler
from tour_guide_bot.helpers.telegram import MenuCommandHandler, SubcommandHandler
from tour_guide_bot.models.guide import Tour


class EditHandler(MenuCommandHandler):
    MENU_ITEMS: list[type[SubcommandHandler]] = [
        AddTranslationHandler,
        RenameHandler,
        section.AddHandler,
        section.RemoveHandler,
    ]

    def get_main_menu_unavailable_text(self, language: str) -> str:
        raise NotImplementedError()

    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-tour", "Edit a tour")

    @classmethod
    def get_main_handlers(cls):
        return [
            CallbackQueryHandler(
                cls.partial(cls.main_entrypoint),
                cls.get_callback_data_pattern(),
            ),
            CallbackQueryHandler(
                cls.partial(cls.back),
                cls.get_callback_data_pattern("root"),
            ),
        ]

    async def get_extra_buttons(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> list[list[InlineKeyboardButton]]:
        return [
            [
                InlineKeyboardButton(
                    t(await self.get_language(update, context)).pgettext(
                        "bot-generic", "« Back"
                    ),
                    callback_data=self.get_callback_data("root"),
                )
            ],
        ]

    async def back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from tour_guide_bot.bot.admin.tour import TourCommandHandler

        await update.callback_query.answer()
        await TourCommandHandler.build_and_run(
            TourCommandHandler.main_entrypoint, update, context
        )

    def get_main_menu_text(self, language: str) -> str:
        return t(language).pgettext(
            "admin-tours", "Please select the tour you want to edit."
        )

    @classmethod
    async def is_available(cls, db_session: AsyncSession) -> bool:
        tours_count: int = await db_session.scalar(select(func.count(Tour.id)))
        return tours_count > 0
