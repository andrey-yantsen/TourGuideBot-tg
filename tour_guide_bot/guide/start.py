from sqlalchemy import select
from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import BaseHandlerCallback
from tour_guide_bot.models.guest import Guest
from tour_guide_bot.models.settings import Settings, SettingsKey


class StartCommandHandler(BaseHandlerCallback):
    STATE_CONTACT = 1

    @classmethod
    def get_handlers(cls):
        return [
            ConversationHandler(
                entry_points=[CommandHandler("start", cls.partial(cls.start))],
                states={
                    cls.STATE_CONTACT: [MessageHandler(filters.CONTACT, cls.partial(cls.contact))],
                },
                fallbacks=[],
                name='guest-init',
                persistent=True
            )
        ]

    @staticmethod
    def request_contact(language: str):
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(
            t(language).pgettext('guest-bot-start', 'Share phone number'),
            request_contact=True
        )]], one_time_keyboard=True)

    async def contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        if update.message.contact.user_id != update.message.from_user.id:
            await update.message.reply_text(t(user.guest_language).pgettext(
                "guest-bot-start", "Please send me your contact number and not somebody else's."),
                reply_markup=self.request_contact(user.guest_language))
            return self.STATE_CONTACT

        user.phone = str(update.message.contact.phone_number)

        stmt = select(Guest).where(Guest.phone == user.phone)
        guest = await self.db_session.scalar(stmt)

        if not guest:
            guest = Guest(phone=user.phone, language=user.language)
            self.db_session.add(guest)

        user.guest = guest
        self.db_session.add(user)
        await self.db_session.commit()

        await update.message.reply_text(t(user.guest_language).pgettext(
            "guest-bot-start", "Added guest."),
            reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        stmt = select(Settings).where((Settings.key == SettingsKey.guide_welcome_message)
                                      & (Settings.language == user.guest_language))
        welcome_message = await self.db_session.scalar(stmt)

        if not welcome_message:
            await update.message.reply_text(t(user.guest_language).pgettext(
                "guest-bot-start", "The bot is not configured yet; please try again later."))
            return ConversationHandler.END

        await update.message.reply_markdown_v2(welcome_message.value)

        if user.guest:
            await update.message.reply_text(t(user.guest_language).pgettext(
                "guest-bot-start", "Found guest early."))
            return ConversationHandler.END
        elif not user.phone:
            await update.message.reply_text(t(user.guest_language).pgettext(
                "guest-bot-start", "I don't recognize you! Please send me your phone number."),
                reply_markup=self.request_contact(user.guest_language))
            return self.STATE_CONTACT
        else:
            stmt = select(Guest).where(Guest.phone == user.phone)
            guest = await self.db_session.scalar(stmt)

            if guest:
                user.guest = guest
                self.db_session.add(user)

                await update.message.reply_text(t(user.guest_language).pgettext(
                    "guest-bot-start", "Found guest."))
            else:
                guest = Guest(phone=user.phone, language=user.language)
                user.guest = guest
                self.db_session.add_all([guest, user])

                await update.message.reply_text(t(user.guest_language).pgettext(
                    "guest-bot-start", "No guest."))

            await self.db_session.commit()
            return ConversationHandler.END
