from functools import partial
from telegram import Update
from telegram.ext import ContextTypes
from tour_guide_bot.models.telegram import TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload


class BaseHandler:
    def __init__(self, db_session):
        self.db_session = db_session
        self.user = None

    @classmethod
    def get_handlers(cls, db):
        raise NotImplementedError()

    @classmethod
    async def build_and_run(cls, db, callback_name, update: Update, context: ContextTypes.DEFAULT_TYPE):
        async with AsyncSession(db, expire_on_commit=False) as session:
            handler = cls(session)
            return await getattr(handler, callback_name)(update, context)

    @classmethod
    def partial(cls, db, callback_name):
        return partial(cls.build_and_run, db, callback_name)

    @staticmethod
    def is_admin_app(context: ContextTypes.DEFAULT_TYPE) -> bool:
        return context.application.__class__.__name__ == 'AdminBot'

    async def get_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
        user = await self.get_user(update, context)

        if self.is_admin_app(context):
            return user.admin_language
        else:
            return user.guest_language

    async def get_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> TelegramUser:
        if self.user:
            return self.user

        stmt = select(TelegramUser).where(TelegramUser.id == update.effective_user.id).options(
            selectinload(TelegramUser.admin), selectinload(TelegramUser.guest))
        user = await self.db_session.scalar(stmt)

        if not user:
            user = TelegramUser(id=update.effective_user.id)

            if update.effective_user.language_code in context.application.enabled_languages:
                user.language = update.effective_user.language_code
            else:
                user.language = context.application.default_language

            self.db_session.add(user)
            await self.db_session.commit()

        self.user = user

        return self.user
