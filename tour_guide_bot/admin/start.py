from sqlalchemy import select
from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import BaseHandler
from tour_guide_bot.models.admin import Admin, AdminPermissions
from . import log


class StartCommandHandler(BaseHandler):
    STATE_CONTACT = 1
    STATE_TOKEN = 2

    @classmethod
    def get_handlers(cls, db):
        return [
            ConversationHandler(
                entry_points=[CommandHandler("start", cls.partial(db, 'start'))],
                states={
                    cls.STATE_CONTACT: [MessageHandler(filters.CONTACT, cls.partial(db, 'contact'))],
                    cls.STATE_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, cls.partial(db, 'token'))],
                },
                fallbacks=[],
                name='admin-init',
                persistent=True
            )
        ]

    @staticmethod
    def request_contact(language: str):
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(
            t(language).pgettext('admin-bot-start', 'Share phone number'),
            request_contact=True
        )]], one_time_keyboard=True)

    async def contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        log.debug('Got contact: %s' % (update, ))
        user = await self.get_user(update, context)

        if update.message.contact.user_id != update.message.from_user.id:
            await update.message.reply_text(t(user.admin_language).pgettext(
                "admin-bot-start", "Please send me your contact number and not somebody else's."),
                reply_markup=self.request_contact(user.admin_language))
            return self.STATE_CONTACT

        user.phone = str(update.message.contact.phone_number)

        stmt = select(Admin).where(Admin.phone == user.phone)
        admin = await self.db_session.scalar(stmt)

        if admin:
            user.admin = admin

        self.db_session.add(user)
        await self.db_session.commit()

        if admin:
            await update.message.reply_text(t(user.admin_language).pgettext(
                "admin-bot-start", "Admin permissions confirmed! Use /help command if you need further help."),
                reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        else:
            await update.message.reply_text(t(user.admin_language).pgettext(
                "admin-bot-start", "I don't think you're in the right place. Please send me the token to confirm ownership."),
                reply_markup=ReplyKeyboardRemove())
            return self.STATE_TOKEN

    async def token(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        log.debug('Got token: %s' % (update, ))
        user = await self.get_user(update, context)

        if update.message.text == context.application.bot.token:
            admin = Admin(phone=user.phone, language=user.admin_language, permissions=AdminPermissions.full)
            user.admin = admin
            self.db_session.add_all([admin, user])
            await self.db_session.commit()

            await update.message.reply_text(t(user.admin_language).pgettext(
                "admin-bot-start", "Admin permissions confirmed! Use /help command if you need further help."))
        else:
            await update.message.reply_text(t(user.admin_language).pgettext(
                "admin-bot-start", "I still don't recognize you, sorry. Try saying /start again when you're ready."))

        return ConversationHandler.END

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        log.debug('Got start command: %s' % (update, ))

        user = await self.get_user(update, context)

        if user.admin:
            await update.message.reply_text(t(user.admin_language).pgettext(
                "admin-bot-start", "You are recognized as an administrator. Please use /help command if you need further help."))
            return ConversationHandler.END
        elif not user.phone:
            await update.message.reply_text(t(user.admin_language).pgettext(
                "admin-bot-start", "I don't recognize you! Please send me your phone number."),
                reply_markup=self.request_contact(user.admin_language))
            return self.STATE_CONTACT
        else:
            stmt = select(Admin).where(Admin.phone == user.phone)
            admin = await self.db_session.scalar(stmt)

            if admin:
                user.admin = admin
                self.db_session.add(user)
                await self.db_session.commit()
                await update.message.reply_text(t(user.admin_language).pgettext(
                    "admin-bot-start", "You are recognized as an administrator. Please use /help command if you need further help."))
                return ConversationHandler.END
            else:
                await update.message.reply_text(t(user.admin_language).pgettext(
                    "admin-bot-start", "I don't think you're in the right place. Please send me the token to confirm ownership."))
                return self.STATE_TOKEN
