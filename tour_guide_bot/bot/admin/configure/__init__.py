from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
)

from tour_guide_bot import t
from tour_guide_bot.bot.admin.configure.audio_to_voice import AudioToVoice
from tour_guide_bot.bot.admin.configure.delay_between_messages import (
    DelayBetweenMessages,
)
from tour_guide_bot.bot.admin.configure.messages.support import SupportMessage
from tour_guide_bot.bot.admin.configure.messages.terms import TermsMessage
from tour_guide_bot.bot.admin.configure.messages.welcome import WelcomeMessage
from tour_guide_bot.helpers.telegram import AdminProtectedBaseHandlerCallback


class ConfigureCommandHandler(AdminProtectedBaseHandlerCallback):
    CONFIGURATION_ITEMS = [
        WelcomeMessage,
        TermsMessage,
        SupportMessage,
        AudioToVoice,
        DelayBetweenMessages,
    ]

    @classmethod
    def get_handlers(cls):
        ret = [CommandHandler("configure", cls.partial(cls.start))]

        for item in cls.CONFIGURATION_ITEMS:
            ret += item.get_handlers()

        return ret

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        keyboard = []

        for item in self.CONFIGURATION_ITEMS:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        item.get_name(user.language),
                        callback_data=item.__name__,
                    )
                ]
            )

        await self.edit_or_reply_text(
            update,
            context,
            t(user.language).pgettext(
                "admin-configure", "Please select the parameter you want to change."
            ),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=keyboard
                + [
                    [
                        InlineKeyboardButton(
                            t(user.language).pgettext("bot-generic", "Abort"),
                            callback_data="cancel",
                        )
                    ],
                ]
            ),
        )
