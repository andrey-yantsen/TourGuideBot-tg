from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot, BotCommand, BotCommandScopeChat

from tour_guide_bot import t
from tour_guide_bot.models.telegram import TelegramUser


class BotCommandsFactory:
    @staticmethod
    async def start(
        bot: Bot, user: TelegramUser, language: str, db_session: AsyncSession
    ):
        commands = []

        commands.append(
            BotCommand(
                "guest",
                t(language).pgettext("admin-bot-command", "Return to the guest mode"),
            )
        )

        commands.append(
            BotCommand(
                "configure",
                t(language).pgettext("admin-bot-command", "Change bot's preferences"),
            )
        )

        commands.append(
            BotCommand(
                "tours",
                t(language).pgettext("admin-bot-command", "Manage your tours"),
            )
        )

        commands.append(
            BotCommand(
                "approve",
                t(language).pgettext(
                    "admin-bot-command", "Grant access to a tour for somebody"
                ),
            )
        )

        commands.append(
            BotCommand(
                "revoke",
                t(language).pgettext(
                    "admin-bot-command", "Revoke access to a tour from somebody"
                ),
            )
        )

        commands.append(
            BotCommand(
                "language",
                t(language).pgettext("admin-bot-command", "Change the language"),
            )
        )

        await bot.set_my_commands(commands, BotCommandScopeChat(user.id))
