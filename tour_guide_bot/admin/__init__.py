import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import BaseHandlerCallback
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__package__)


class AdminProtectedBaseHandlerCallback(BaseHandlerCallback):
    @classmethod
    async def build_and_run(cls, callback, update: Update, context: ContextTypes.DEFAULT_TYPE):
        async with AsyncSession(context.application.db_engine, expire_on_commit=False) as session:
            handler = cls(session)

            user = await handler.get_user(update, context)

            if not user.admin:
                if update.message:
                    await update.message.reply_text(t(user.language).pgettext('admin-bot', 'Access denied.'))
                return ConversationHandler.END

            return await callback(handler, update, context)
