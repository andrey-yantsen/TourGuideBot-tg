from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
from tour_guide_bot.helpers.telegram import ConfigureSubcommandHandler
from tour_guide_bot.models.settings import Settings, SettingsKey


class PaymentsSubcommand(ConfigureSubcommandHandler):
    CONFIGURATION_ITEMS = [
        AddPaymentProvider,
        ChangePaymentProvider,
        DeletePaymentProvider,
    ]

    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-configure", "Payments")

    @classmethod
    def get_handlers(cls):
        ret = [
            CallbackQueryHandler(
                cls.partial(cls.start),
                "^" + cls.__name__ + "$",
            ),
            CallbackQueryHandler(
                cls.partial(cls.back),
                "^" + cls.__name__ + ":root$",
            ),
        ]
        for item in cls.CONFIGURATION_ITEMS:
            ret += item.get_handlers()

        return ret

    async def back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from tour_guide_bot.bot.admin.configure import ConfigureCommandHandler

        await update.callback_query.answer()
        await ConfigureCommandHandler.build_and_run(
            ConfigureCommandHandler.start, update, context
        )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        terms_and_support_exists = True
        for lang in context.application.enabled_languages:
            terms_and_support_exists = terms_and_support_exists and (
                await Settings.exists(
                    self.db_session,
                    [SettingsKey.terms_message, SettingsKey.support_message],
                    lang,
                )
            )

        keyboard = []
        if terms_and_support_exists:
            msg = t(user.language).pgettext(
                "admin-configure",
                "Please select the payment-related parameter you want to change.",
            )

            for item in self.CONFIGURATION_ITEMS:
                if not await item.available(self.db_session):
                    continue

                keyboard.append(
                    [
                        InlineKeyboardButton(
                            item.get_name(user.language),
                            callback_data=item.__name__,
                        )
                    ]
                )
        else:
            msg = t(user.language).pgettext(
                "admin-configure",
                "You need to set up Terms & Conditions and support messages first.",
            )

        await update.callback_query.answer()
        await self.edit_or_reply_text(
            update,
            context,
            msg,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=keyboard
                + [
                    [
                        InlineKeyboardButton(
                            t(user.language).pgettext("bot-generic", "« Back"),
                            callback_data=self.__class__.__name__ + ":root",
                        )
                    ],
                ]
            ),
        )
