from telegram.ext import (
    BaseHandler,
    CommandHandler,
)

from tour_guide_bot import t
from tour_guide_bot.bot.admin.tour.add import AddHandler
from tour_guide_bot.bot.admin.tour.delete import DeleteHandler
from tour_guide_bot.bot.admin.tour.edit import EditHandler
from tour_guide_bot.bot.admin.tour.pricing import PricingHandler
from tour_guide_bot.helpers.telegram import MenuCommandHandler, SubcommandHandler


class TourCommandHandler(MenuCommandHandler):
    def get_main_menu_unavailable_text(self, language: str) -> str:
        raise NotImplementedError()

    MENU_ITEMS: list[type[SubcommandHandler]] = [
        AddHandler,
        PricingHandler,
        EditHandler,
        DeleteHandler,
    ]

    def get_main_menu_text(self, language: str) -> str:
        return t(language).pgettext("admin-tour", "Please select an action.")

    @classmethod
    def get_main_handlers(cls) -> list[BaseHandler]:
        return [
            CommandHandler("tours", cls.partial(cls.main_entrypoint)),
        ]
