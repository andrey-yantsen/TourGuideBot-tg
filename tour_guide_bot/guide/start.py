from datetime import datetime
from sqlalchemy import func, select
from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from tour_guide_bot import t
from tour_guide_bot.helpers.language import LanguageHandler
from tour_guide_bot.helpers.telegram import BaseHandlerCallback
from tour_guide_bot.models.guest import BoughtTours, Guest
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
                fallbacks=[
                    MessageHandler(filters.TEXT & ~filters.COMMAND, cls.partial(cls.unexpected_message))
                ] + LanguageHandler.get_handlers() + [
                    MessageHandler(filters.COMMAND, cls.partial(cls.unexpected_command))
                ],
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

    async def unexpected_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)
        await update.message.reply_text(t(user.guest_language).pgettext('guest-bot-start', 'Please send me your phone'
                                                                        ' number using the "Share phone number" button.'))

    async def unexpected_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)
        await update.message.reply_text(t(user.guest_language).pgettext('guest-bot-start', 'Unexpected command '
                                                                        'received. At this stage you can only use '
                                                                        '/language to change the interface language.'))

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

        await self.process_guest(guest, update, context)
        return ConversationHandler.END

    async def process_guest(self, guest: Guest, update: Update, context: ContextTypes.DEFAULT_TYPE):
        active_tours_cnt = await self.db_session.scalar(select(func.count(BoughtTours.id)).where(
            (BoughtTours.guest == guest)
            & (BoughtTours.expire_ts >= datetime.now())
        ))
        language = await self.get_language(update, context)

        if active_tours_cnt:
            await update.message.reply_text(t(language).pgettext('guest-bot-start', 'I see you have some tours available; thank you the support! '
                                                                 'Send /tours to start exploring!'), reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text(t(language).pgettext('guest-tour', 'Unfortunately, no tours are available for you at the moment.'
                                                                 ' Approving somebody for a tour takes a while, but if you feel like a mistake was made'
                                                                 " don't hesitate contacting me! The bot's profile should provide with all the required info."),
                                            reply_markup=ReplyKeyboardRemove())

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
            await self.process_guest(user.guest, update, context)
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
            else:
                guest = Guest(phone=user.phone, language=user.language)
                user.guest = guest
                self.db_session.add_all([guest, user])

            await self.process_guest(guest, update, context)
            await self.db_session.commit()
            return ConversationHandler.END
