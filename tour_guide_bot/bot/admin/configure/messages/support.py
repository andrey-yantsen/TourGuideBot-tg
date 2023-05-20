from tour_guide_bot import t
from tour_guide_bot.bot.admin.configure.messages import MessagesBase
from tour_guide_bot.models.settings import SettingsKey


class SupportMessage(MessagesBase):
    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-configure", "Support message")

    @staticmethod
    def get_message_name(language: str) -> str:
        return t(language).pgettext("admin-configure", "support message")

    @staticmethod
    def get_message_settings_key() -> SettingsKey:
        return SettingsKey.support_message
