from tour_guide_bot import t
from tour_guide_bot.bot.admin.configure.messages import MessagesBase
from tour_guide_bot.models.settings import SettingsKey


class TermsMessage(MessagesBase):
    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-configure", "Terms & Conditions")

    @staticmethod
    def get_message_name(language: str) -> str:
        return t(language).pgettext("admin-configure", "terms & conditions")

    @staticmethod
    def get_message_settings_key() -> SettingsKey:
        return SettingsKey.terms_message
