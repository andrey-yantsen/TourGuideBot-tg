from functools import partial
from telegram import Update
from telegram.ext import ContextTypes
from tour_guide_bot.models.telegram import TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload


class BaseHandler:
    def __init__(self, app, db_session):
        self.db_session = db_session
        self.app = app
        self.user = None

    @classmethod
    async def build_and_run(cls, app, db, callback_name, update: Update, context: ContextTypes.DEFAULT_TYPE):
        async with AsyncSession(db, expire_on_commit=False) as session:
            handler = cls(app, session)
            return await getattr(handler, callback_name)(update, context)

    @classmethod
    def partial(cls, app, db, callback_name):
        return partial(cls.build_and_run, app, db, callback_name)

    async def get_user(self, update: Update) -> TelegramUser:
        if self.user:
            return self.user

        stmt = select(TelegramUser).where(TelegramUser.id == update.message.from_user.id).options(
            selectinload(TelegramUser.admin), selectinload(TelegramUser.guest))
        user = await self.db_session.scalar(stmt)

        if not user:
            user = TelegramUser(id=update.message.from_user.id, language=update.message.from_user.language_code)
            self.db_session.add(user)
            await self.db_session.commit()

        self.user = user

        return self.user
