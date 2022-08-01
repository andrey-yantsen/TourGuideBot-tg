from datetime import datetime
from typing import Optional
from regex import E
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaAudio, InputMediaPhoto, InputMediaVideo, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler
from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import BaseHandlerCallback, get_tour_title
from tour_guide_bot.models.guide import BoughtTours, MessageType, Tour, TourSection, TourTranslation
from . import log


class ToursCommandHandler(BaseHandlerCallback):
    STATE_SELECT_TOUR = 1
    STATE_TOUR_IN_PROGRESS = 2

    @classmethod
    def get_handlers(cls):
        return [
            ConversationHandler(
                entry_points=[CommandHandler("tours", cls.partial(cls.start))],
                states={
                    cls.STATE_SELECT_TOUR: [
                        CallbackQueryHandler(cls.partial(cls.start_tour), '^start_tour:(\d+):(\s+)$'),
                    ],
                    cls.STATE_TOUR_IN_PROGRESS: [
                        CallbackQueryHandler(cls.partial(cls.tour_change_section),
                                             '^tour_change_section:(\d+):(\d+)$'),
                    ],
                },
                fallbacks=[
                    CommandHandler('cancel', cls.partial(cls.cancel)),
                    CallbackQueryHandler(cls.partial(cls.cancel), 'cancel'),
                ],
                name='guest-tour',
                persistent=True
            )
        ]

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        await self.edit_or_reply_text(update, context, t(user.admin_language).pgettext(
            'bot-generic', 'Cancelled.'))

        return ConversationHandler.END

    async def get_tour(self, guest_id: int, tour_id: int) -> Optional[BoughtTours]:
        bought_tour = await self.db_session.scalar(
            select(BoughtTours).options(selectinload(BoughtTours.tour).selectinload(Tour.translation))
            .where((BoughtTours.guest_id == guest_id)
                   & (BoughtTours.tour_id == tour_id)
                   & (BoughtTours.expire_ts >= datetime.now()))
        )

        return bought_tour

    async def display_section(self, translation: TourTranslation, position: int, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.callback_query:
            await update.callback_query.delete_message()

        user = await self.get_user(update, context)

        if position < 0 or len(translation.section) <= position:
            await self.edit_or_reply_text(update, context, t(user.admin_language).pgettext(
                'bot-generic', 'Something went wrong; please try again.'))
            return

        section = translation.section[position]

        bot = context.bot
        chat_id = update.effective_chat.id

        for content in section.content:
            match content.message_type:
                case MessageType.text:
                    await bot.send_message(chat_id, content.content['text'], ParseMode.MARKDOWN_V2, disable_web_page_preview=True)

                case MessageType.location:
                    await bot.send_location(chat_id, content.content['latitude'], content.content['longitude'])

                case MessageType.voice:
                    await bot.send_voice(chat_id, content.content['files'][0]['file_id'], caption=content.content['files'][0].get('caption'), parse_mode=ParseMode.MARKDOWN_V2)

                case MessageType.video_note:
                    await bot.send_video_note(chat_id, content.content['files'][0]['file_id'], caption=content.content['files'][0].get('caption'), parse_mode=ParseMode.MARKDOWN_V2)

                case MessageType.audio:
                    await bot.send_audio(chat_id, content.content['files'][0]['file_id'], caption=content.content['files'][0].get('caption'), parse_mode=ParseMode.MARKDOWN_V2)

                case MessageType.video:
                    await bot.send_video(chat_id, content.content['files'][0]['file_id'], caption=content.content['files'][0].get('caption'), parse_mode=ParseMode.MARKDOWN_V2)

                case MessageType.photo:
                    await bot.send_photo(chat_id, content.content['files'][0]['file_id'], caption=content.content['files'][0].get('caption'), parse_mode=ParseMode.MARKDOWN_V2)

                case MessageType.media_group:
                    media_group = []

                    for f in content.content['files']:
                        match MessageType[f['type']]:
                            case MessageType.audio:
                                media_group.append(InputMediaAudio(
                                    f['file_id'], caption=f.get('caption'), parse_mode=ParseMode.MARKDOWN_V2))
                            case MessageType.video:
                                media_group.append(InputMediaVideo(
                                    f['file_id'], caption=f.get('caption'), parse_mode=ParseMode.MARKDOWN_V2))
                            case MessageType.photo:
                                media_group.append(InputMediaPhoto(
                                    f['file_id'], caption=f.get('caption'), parse_mode=ParseMode.MARKDOWN_V2))

                    await bot.send_media_group(chat_id, media_group)

        if position < len(translation.section) - 1:
            await self.reply_text(update, context, t(user.guest_language).pgettext(
                'guide-tour', 'Are you ready to continue?'), reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(t(user.guest_language).pgettext(
                        'guide-tour', 'Next section'), callback_data='tour_change_section:%d:%d' % (translation.id, position + 1))],
                    [InlineKeyboardButton(t(user.guest_language).pgettext(
                        'bot-generic', 'Abort'), callback_data='cancel')],
                ]))
            return self.STATE_TOUR_IN_PROGRESS

        return ConversationHandler.END

    async def display_first_section(self, tour: Tour, update: Update, context: ContextTypes.DEFAULT_TYPE):
        translations = {
            translation.language: translation
            for translation in tour.translation
        }

        user = await self.get_user(update, context)

        if user.guest_language not in translations:
            log.warning(t().pgettext('cli', "Tour #{0} doesn't have a language {1} preferred by the user {2}.".format(
                tour.id, user.guest_language, user.id)))
            if context.application.default_language not in translations:
                log.error(t().pgettext('cli', "Tour #{0} doesn't have a default app language {1}.".format(
                    tour.id, context.application.default_language)))
                await self.edit_or_reply_text(update, context, t(user.admin_language).pgettext(
                    'bot-generic', 'Something went wrong; please try again.'))
                return ConversationHandler.END
            else:
                translation = translations[context.application.default_language]
        else:
            translation = translations[user.guest_language]

        return await self.display_section(translation, 0, update, context)

    async def start_tour(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        bought_tour = await self.get_tour(user.guest_id, int(context.matches[0].gorup(1)))
        if not bought_tour:
            await self.edit_or_reply_text(update, context, t(user.guest_language).pgettext(
                'guide-tour', "Unfortunately, you don't have access to the requested tour."))

            return ConversationHandler.END

        return await self.display_first_section(bought_tour.tour, update, context)

    async def tour_change_section(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        translation = await self.db_session.scalar(select(TourTranslation).options(selectinload(TourTranslation.section).selectinload(TourSection.content)))
        if not translation:
            await self.edit_or_reply_text(update, context, t(user.admin_language).pgettext(
                'bot-generic', 'Something went wrong; please try again.'))
            return

        bought_tour = await self.get_tour(user.guest_id, translation.tour_id)
        if not bought_tour:
            await self.edit_or_reply_text(update, context, t(user.guest_language).pgettext(
                'guide-tour', "Unfortunately, you don't have access to the requested tour."))

            return ConversationHandler.END

        return await self.display_section(translation, int(context.matches[0].group(2)), update, context)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)
        language = user.guest_language

        # TODO: rewrite this
        # Currently done in the stupidiest way possible for self.display_first_section()
        bought_tours = await self.db_session.scalars(
            select(BoughtTours).options(selectinload(BoughtTours.tour).selectinload(
                Tour.translation).selectinload(TourTranslation.section).selectinload(TourSection.content))
            .where((BoughtTours.guest == user.guest) & (BoughtTours.expire_ts >= datetime.now()))
        )

        keyboard = []

        last_tour = None
        for bought_tour in bought_tours:
            title = get_tour_title(bought_tour.tour, language, context)
            keyboard.append([InlineKeyboardButton(title, callback_data='start_tour:%s:%s' %
                            (bought_tour.tour_id, language))])
            last_tour = bought_tour.tour

            if not bought_tour.is_user_notified:
                bought_tour.is_user_notified = True
                self.db_session.add(bought_tour)

        await self.db_session.commit()

        if len(keyboard) == 0:
            await update.message.reply_text(t(language).pgettext('guest-tour', "Unfortunately, no tours are available for"
                                                                 " you at the moment. Approving somebody for a tour takes"
                                                                 " a while, but if you feel like a mistake was made, don't"
                                                                 " hesitate to contact me! The bot's profile should provide"
                                                                 " all the required info."))

            return ConversationHandler.END
        elif len(keyboard) == 1:
            return await self.display_first_section(last_tour, update, context)

        keyboard.append([InlineKeyboardButton(t(language).pgettext('bot-generic', 'Abort'), callback_data='cancel')])

        await update.message.reply_text(t(language).pgettext('guide-tour', 'Please select a tour you want to start.'),
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return self.STATE_SELECT_TOUR
