from telegram.ext import BaseHandler

from tour_guide_bot.helpers.telegram import SubcommandHandler


class AddHandler(SubcommandHandler):
    @staticmethod
    def get_name(language: str) -> str:
        raise NotImplementedError()

    @classmethod
    def get_handlers(cls) -> list[BaseHandler]:
        return []
