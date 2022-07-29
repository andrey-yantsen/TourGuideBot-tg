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
    def get_handlers(cls, app, db):
        raise NotImplementedError()

    @classmethod
    async def build_and_run(cls, app, db, callback_name, update: Update, context: ContextTypes.DEFAULT_TYPE):
        async with AsyncSession(db, expire_on_commit=False) as session:
            handler = cls(app, session)
            return await getattr(handler, callback_name)(update, context)

    @classmethod
    def partial(cls, app, db, callback_name):
        return partial(cls.build_and_run, app, db, callback_name)

    @property
    def is_admin_app(self) -> bool:
        return self.app.__class__.__name__ == 'AdminBot'

    async def get_language(self, update: Update) -> str:
        user = await self.get_user(update)

        if self.is_admin_app:
            return user.admin_language
        else:
            return user.guest_language

    async def get_user(self, update: Update) -> TelegramUser:
        if self.user:
            return self.user

        stmt = select(TelegramUser).where(TelegramUser.id == update.effective_user.id).options(
            selectinload(TelegramUser.admin), selectinload(TelegramUser.guest))
        user = await self.db_session.scalar(stmt)

        if not user:
            user = TelegramUser(id=update.effective_user.id)

            if update.effective_user.language_code in self.app.enabled_languages:
                user.language = update.effective_user.language_code
            else:
                user.language = self.app.default_language

            self.db_session.add(user)
            await self.db_session.commit()

        self.user = user

        return self.user
