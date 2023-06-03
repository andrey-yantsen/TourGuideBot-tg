from telegram.ext import BaseHandler

from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import SubcommandHandler


class RemoveHandler(SubcommandHandler):
    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-tour", "")

    @classmethod
    def get_handlers(cls) -> list[BaseHandler]:
        return []
