from telegram import Update
from telegram.ext import ContextTypes
from tour_guide_bot.models.telegram import TelegramUser
from sqlalchemy.orm import Session
from sqlalchemy import select
from . import log


class StartCommandHandler:
    def __init__(self, db):
        self.db = db

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        with Session(self.db) as session:
            stmt = select(TelegramUser).where(TelegramUser.id == update.message.from_user.id)
            print(stmt)
            user = session.scalar(stmt)
            print(user)

        log.debug('Got start command: %s' % (update, ))
