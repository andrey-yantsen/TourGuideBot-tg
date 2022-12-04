from telegram import Bot, BotCommand, BotCommandScopeChat

from tour_guide_bot import t
from tour_guide_bot.models.telegram import TelegramUser


class BotCommandsFactory:
    @staticmethod
    async def start(bot: Bot, user: TelegramUser, language: str):
        commands = []

        if user.admin:
            commands.append(
                BotCommand(
                    "admin",
                    t(language).pgettext("guest-bot-command", "Enter admin mode"),
                )
            )

        commands.append(
            BotCommand(
                "tours",
                t(language).pgettext("guest-bot-command", "Show available tours"),
            )
        )

        commands.append(
            BotCommand(
                "language",
                t(language).pgettext("guest-bot-command", "Change the language"),
            )
        )

        commands.append(
            BotCommand(
                "start",
                t(language).pgettext(
                    "guest-bot-command", "Display the welcome message again"
                ),
            )
        )

        await bot.set_my_commands(commands, BotCommandScopeChat(user.id))
