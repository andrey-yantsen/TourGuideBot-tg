from telegram import InlineKeyboardButton, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
)

from tour_guide_bot import t
from tour_guide_bot.bot.admin.configure.payments.payment_provider.add import (
    AddPaymentProvider,
)
from tour_guide_bot.bot.admin.configure.payments.payment_provider.change import (
    ChangePaymentProvider,
)
from tour_guide_bot.bot.admin.configure.payments.payment_provider.delete import (
    DeletePaymentProvider,
)
from tour_guide_bot.helpers.telegram import MenuCommandHandler, SubcommandHandler
from tour_guide_bot.models.settings import Settings, SettingsKey


class PaymentsSubcommand(MenuCommandHandler, SubcommandHandler):
    MENU_ITEMS = [
        AddPaymentProvider,
        ChangePaymentProvider,
        DeletePaymentProvider,
    ]

    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-configure", "Payments")

    @classmethod
    def get_main_handlers(cls):
        return [
            CallbackQueryHandler(
                cls.partial(cls.main_entrypoint),
                "^" + cls.__name__ + "$",
            ),
            CallbackQueryHandler(
                cls.partial(cls.back),
                "^" + cls.__name__ + ":root$",
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
                    callback_data=self.__class__.__name__ + ":root",
                )
            ],
        ]

    async def back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from tour_guide_bot.bot.admin.configure import ConfigureCommandHandler

        await update.callback_query.answer()
        await ConfigureCommandHandler.build_and_run(
            ConfigureCommandHandler.main_entrypoint, update, context
        )

    def get_main_menu_text(self, language: str) -> str:
        return t(language).pgettext(
            "admin-configure",
            "Please select the payment-related parameter you want to change.",
        )

    def get_main_menu_unavailable_text(self, language: str) -> str:
        return t(language).pgettext(
            "admin-configure",
            "You need to set up Terms & Conditions and support messages first.",
        )

    async def is_menu_available(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        terms_and_support_exists = True
        # TODO: optimize the query
        for lang in context.application.enabled_languages:
            terms_and_support_exists = terms_and_support_exists and (
                await Settings.exists(
                    self.db_session,
                    [SettingsKey.terms_message, SettingsKey.support_message],
                    lang,
                )
            )
        return terms_and_support_exists
