from abc import ABC

import aiohttp_session
from aiohttp.web import HTTPForbidden, HTTPTemporaryRedirect, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tour_guide_bot.models.telegram import TelegramUser


class Base(ABC):
    __slots__ = ("telegram_user",)

    async def auth(self, request: Request):
        http_session = await aiohttp_session.get_session(request)

        if "user_info" not in http_session:
            raise HTTPTemporaryRedirect(location="/")

        async with AsyncSession(request.app.db_engine) as db_session:
            user: TelegramUser | None = await db_session.scalar(
                select(TelegramUser)
                .where(TelegramUser.id == int(http_session["user_info"].get("id", "0")))
                .options(
                    selectinload(TelegramUser.guest), selectinload(TelegramUser.admin)
                )
            )

        if not user or not user.admin:
            raise HTTPForbidden(
                text="Please tell /admin to the bot and refresh the page."
            )
