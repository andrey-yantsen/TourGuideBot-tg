from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from tour_guide_bot import t
from tour_guide_bot.helpers.telegram import get_tour_title, AdminProtectedBaseHandlerCallback
from tour_guide_bot.models.guide import MessageType, Tour, TourSection, TourSectionContent, TourTranslation
from . import log


class TourCommandHandler(AdminProtectedBaseHandlerCallback):
    STATE_SELECT_ACTION = 1
    STATE_TOUR_ADD_LANGUAGE = 2
    STATE_TOUR_SAVE_TITLE = 3
    STATE_TOUR_ADD_CONTENT = 4
    STATE_TOUR_EDIT_SELECT_ACTION = 5
    STATE_TOUR_DELETE_CONFIRM = 6
    STATE_TOUR_DELETE = 7

    CALLBACK_DATA_ADD_TOUR = 'add_tour'
    CALLBACK_DATA_EDIT_TOUR = 'edit_tour'
    CALLBACK_DATA_DELETE_TOUR = 'delete_tour'

    CALLBACK_DATA_DELETE_TOUR_CONFIRMED = 'delete_tour_confirmed'

    @classmethod
    def get_handlers(cls):
        return [
            ConversationHandler(
                entry_points=[CommandHandler('tours', cls.partial(cls.start))],
                states={
                    cls.STATE_SELECT_ACTION: [
                        CallbackQueryHandler(cls.partial(cls.request_tour_language), '^%s$' %
                                             (cls.CALLBACK_DATA_ADD_TOUR, )),
                        CallbackQueryHandler(cls.partial(cls.select_tour), '^%s$' % (cls.CALLBACK_DATA_EDIT_TOUR, )),
                        CallbackQueryHandler(cls.partial(cls.select_tour), '^%s$' % (cls.CALLBACK_DATA_DELETE_TOUR, )),
                    ],
                    cls.STATE_TOUR_DELETE_CONFIRM: [
                        CallbackQueryHandler(cls.partial(cls.request_delete_tour_confirmation), '^%s:(\d+)$' %
                                             (cls.CALLBACK_DATA_DELETE_TOUR, )),
                    ],
                    cls.STATE_TOUR_DELETE: [
                        CallbackQueryHandler(cls.partial(cls.delete_tour), '^%s:(\d+)$' %
                                             (cls.CALLBACK_DATA_DELETE_TOUR_CONFIRMED, )),
                    ],
                    cls.STATE_TOUR_ADD_LANGUAGE: [
                        CallbackQueryHandler(cls.partial(cls.request_tour_title), '^tour_language:(.*)$'),
                    ],
                    cls.STATE_TOUR_SAVE_TITLE: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, cls.partial(cls.save_tour_translation)),
                    ],
                    cls.STATE_TOUR_ADD_CONTENT: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, cls.partial(
                            cls.translation_section_content_add_text)),
                        MessageHandler(filters.LOCATION, cls.partial(cls.translation_section_content_add_location)),
                        MessageHandler(filters.AUDIO, cls.partial(cls.translation_section_content_add_audio)),
                        MessageHandler(filters.VOICE, cls.partial(cls.translation_section_content_add_voice)),
                        MessageHandler(filters.VIDEO, cls.partial(cls.translation_section_content_add_video)),
                        MessageHandler(filters.VIDEO_NOTE, cls.partial(cls.translation_section_content_add_video_note)),
                        MessageHandler(filters.PHOTO, cls.partial(cls.translation_section_content_add_photo)),
                        MessageHandler(filters.ALL & ~filters.COMMAND, cls.partial(cls.translation_unknown_content)),
                        CommandHandler('done', cls.partial(cls.tour_add_content_done)),
                    ],
                },
                fallbacks=[
                    CommandHandler('cancel', cls.partial(cls.cancel)),
                    CallbackQueryHandler(cls.partial(cls.cancel), 'cancel'),
                    MessageHandler(filters.COMMAND, cls.partial(cls.unknown_command)),
                ],
                name='admin-tour',
                persistent=True
            )
        ]

    async def cleanup_context(self, context: ContextTypes.DEFAULT_TYPE):
        for key in ('tour_language', 'tour_id', 'action'):
            if key in context.user_data:
                del context.user_data[key]

        await self.cleanup_context_tour_translation(context)

    async def cleanup_context_tour_translation(self, context: ContextTypes.DEFAULT_TYPE):
        for key in ('tour_translation_id', ):
            if key in context.user_data:
                del context.user_data[key]

        await self.cleanup_context_tour_translation_section(context)

    async def cleanup_context_tour_translation_section(self, context: ContextTypes.DEFAULT_TYPE):
        if 'tour_section_id' in context.user_data:
            tour_section_id = context.user_data.pop('tour_section_id')
            tour_section = await self.db_session.scalar(select(TourSection).where(TourSection.id == tour_section_id).options(selectinload(TourSection.content)))

            if len(tour_section.content) == 0:
                await self.db_session.delete(tour_section)
                await self.db_session.commit()

        for key in ('tour_section_content_position', 'tour_section_position'):
            if key in context.user_data:
                del context.user_data[key]

    async def tour_add_content_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)
        position = context.user_data.get('tour_section_content_position', 0)
        tour_section_position = context.user_data.get('tour_section_position', 0)

        await self.cleanup_context_tour_translation_section(context)

        if context.user_data.get('action') == 'edit':
            return ConversationHandler.END

        if position == 0:
            await self.cleanup_context(context)
            await update.message.reply_text(t(user.admin_language).pgettext('admin-tours', "Done!"))
            return ConversationHandler.END

        tour_section = TourSection(
            tour_translation_id=context.user_data['tour_translation_id'], position=tour_section_position + 1)
        self.db_session.add(tour_section)
        await self.db_session.commit()
        context.user_data['tour_section_id'] = tour_section.id
        context.user_data['tour_section_position'] = tour_section_position + 1

        await update.message.reply_text(t(user.admin_language).pgettext('admin-tours', "Done! Send more content for the next"
                                                                        " tour section, or send /done if you're finished."))

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)
        await self.cleanup_context(context)
        await self.edit_or_reply_text(update, context, t(user.admin_language).pgettext('bot-generic', 'Cancelled.'))
        return ConversationHandler.END

    async def translation_section_content_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message_type: MessageType, text=None,
                                              file_id: Optional[str] = None, file_caption=None, location=None):
        is_first = True
        async with context.application.content_add_lock:
            if update.message.media_group_id:
                content = await self.db_session.scalar(select(TourSectionContent)
                                                       .where((TourSectionContent.tour_section_id == context.user_data['tour_section_id'])
                                                              & (TourSectionContent.media_group_id == update.message.media_group_id)))

                if content:
                    is_first = False

                    file = {
                        'file_id': file_id,
                        'message_id': update.message.message_id,
                        'type': message_type.name,
                    }

                    if file_caption:
                        file['caption'] = file_caption

                    files = content.content.pop('files')
                    files.append(file)

                    content.content['files'] = list(sorted(
                        files,
                        key=lambda file: file['message_id']
                    ))

                    self.db_session.add(content)

            if is_first:
                is_first = True
                content = TourSectionContent()
                content.tour_section_id = context.user_data['tour_section_id']
                if update.message.media_group_id:
                    content.media_group_id = update.message.media_group_id
                    content.message_type = MessageType.media_group
                else:
                    content.message_type = message_type

                content.position = context.user_data.get('tour_section_content_position', 0)

                if file_id:
                    file = {
                        'file_id': file_id,
                        'message_id': update.message.message_id,
                        'type': message_type.name,
                    }

                    if file_caption:
                        file['caption'] = file_caption

                    content.content = {'files': [file]}
                elif text:
                    content.content = {'text': text}
                elif location:
                    content.content = location

                self.db_session.add(content)

        await self.db_session.commit()

        context.user_data['tour_section_content_position'] = context.user_data.get(
            'tour_section_content_position', 0) + 1
        return is_first

    async def translation_section_content_add_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.translation_section_content_add(update, context, MessageType.text, text=update.message.text_markdown_v2_urled)
        language = await self.get_language(update, context)
        message = t(language).pgettext('admin-tours', 'The text was added to the section!')
        message += ' '
        message += t(language).pgettext('admin-tours',
                                        "Add more data or send /done if you're finished with the section.")
        await update.message.reply_text(message)

    async def translation_section_content_add_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.translation_section_content_add(update, context, MessageType.location, location={
            'latitude': update.message.location.latitude,
            'longitude': update.message.location.longitude,
        })
        language = await self.get_language(update, context)
        message = t(language).pgettext('admin-tours', 'The location was added to the section!')
        message += ' '
        message += t(language).pgettext('admin-tours',
                                        "Add more data or send /done if you're finished with the section.")
        await update.message.reply_text(message)

    async def translation_section_content_add_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.translation_section_content_add(update, context, MessageType.voice,
                                                   file_id=update.message.voice.file_id,
                                                   file_caption=update.message.caption_markdown_v2_urled)

        language = await self.get_language(update, context)
        message = t(language).pgettext('admin-tours', 'The voice was added to the section!')
        message += ' '
        message += t(language).pgettext('admin-tours',
                                        "Add more data or send /done if you're finished with the section.")
        await update.message.reply_text(message)

    async def translation_section_content_add_video_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.translation_section_content_add(update, context, MessageType.video_note,
                                                   file_id=update.message.video_note.file_id,
                                                   file_caption=update.message.caption_markdown_v2_urled)

        language = await self.get_language(update, context)
        message = t(language).pgettext('admin-tours', 'The video note was added to the section!')
        message += ' '
        message += t(language).pgettext('admin-tours',
                                        "Add more data or send /done if you're finished with the section.")
        await update.message.reply_text(message)

    async def translation_section_content_add_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        is_first = await self.translation_section_content_add(update, context, MessageType.audio,
                                                              file_id=update.message.audio.file_id,
                                                              file_caption=update.message.caption_markdown_v2_urled)

        if is_first:
            language = await self.get_language(update, context)
            message = t(language).pgettext('admin-tours', 'The audio was added to the section!')
            message += ' '
            message += t(language).pgettext('admin-tours',
                                            "Add more data or send /done if you're finished with the section.")

            if update.message.media_group_id:
                message += ' '
                message += t(language).pgettext('admin-tours',
                                                'Please wait until all audios in the group are uploaded before proceeding to the next section.')

            await update.message.reply_text(message)

    async def translation_section_content_add_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        is_first = await self.translation_section_content_add(update, context, MessageType.video,
                                                              file_id=update.message.video.file_id,
                                                              file_caption=update.message.caption_markdown_v2_urled)

        if is_first:
            language = await self.get_language(update, context)
            message = t(language).pgettext('admin-tours', 'The video was added to the section!')
            message += ' '
            message += t(language).pgettext('admin-tours',
                                            "Add more data or send /done if you're finished with the section.")

            if update.message.media_group_id:
                message += ' '
                message += t(language).pgettext('admin-tours',
                                                'Please wait until all videos in the group are uploaded before proceeding to the next section.')

            await update.message.reply_text(message)

    async def translation_section_content_add_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        sorted_photos = list(
            sorted(update.message.photo,
                   key=lambda photo: photo['width'] * photo['height'],
                   reverse=True))

        is_first = await self.translation_section_content_add(update, context, MessageType.photo,
                                                              file_id=sorted_photos[0].file_id,
                                                              file_caption=update.message.caption_markdown_v2_urled)

        if is_first:
            language = await self.get_language(update, context)
            message = t(language).pgettext('admin-tours', 'The photo was added to the section!')
            message += ' '
            message += t(language).pgettext('admin-tours',
                                            "Add more data or send /done if you're finished with the section.")

            if update.message.media_group_id:
                message += ' '
                message += t(language).pgettext('admin-tours',
                                                'Please wait until all photos in the group are uploaded before proceeding to the next section.')

            await update.message.reply_text(message)

    async def translation_unknown_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        language = (await self.get_user(update, context)).admin_language
        await update.message.reply_text(t(language).pgettext('admin-tours', 'Unsupported message! Please send me one of the'
                                                             ' following to add to the tour section: location, text,'
                                                             ' photo, audio, video, voice or video note.'))

    async def delete_tour(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)
        tour = await self.db_session.scalar(select(Tour)
                                            .where(Tour.id == context.matches[0].group(1))
                                            .options(selectinload(Tour.translation)))

        if not tour:
            await self.edit_or_reply_text(update, context, t(user.admin_language).pgettext(
                'bot-generic', 'Something went wrong; please try again.'))
            await self.cleanup_context(context)
            return ConversationHandler.END

        tour_title = get_tour_title(tour, user.admin_language, context)

        await self.db_session.delete(tour)
        await self.db_session.commit()

        await update.callback_query.edit_message_text(t(user.admin_language).pgettext(
            'admin-tours', 'The tour "{0}" was removed.'.format(tour_title)))
        await self.cleanup_context(context)
        return ConversationHandler.END

    async def request_delete_tour_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)
        tour = await self.db_session.scalar(select(Tour)
                                            .where(Tour.id == context.matches[0].group(1))
                                            .options(selectinload(Tour.translation)))

        if not tour:
            await self.edit_or_reply_text(update, context, t(user.admin_language).pgettext(
                'bot-generic', 'Something went wrong; please try again.'))
            await self.cleanup_context(context)
            return ConversationHandler.END

        await update.callback_query.edit_message_text(t(user.admin_language).pgettext(
            'admin-tours', 'Do you really want to delete the tour "{0}"?'.format(get_tour_title(tour, user.admin_language, context))),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(t(user.admin_language).pgettext('bot-generic',
                                                                         'Yes'), callback_data='%s:%d' % (self.CALLBACK_DATA_DELETE_TOUR_CONFIRMED, tour.id)),
                    InlineKeyboardButton(t(user.admin_language).pgettext(
                        'bot-generic', 'Abort'), callback_data='cancel')
                ],
            ]))
        return self.STATE_TOUR_DELETE

    async def save_tour_translation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        if 'tour_id' in context.user_data:
            tour = await self.db_session.scalar(select(Tour).where(Tour.id == context.user_data['tour_id']))
        else:
            tour = Tour()
            self.db_session.add(tour)

        is_new_translation = True
        if 'tour_translation_id' in context.user_data:
            is_new_translation = False
            tour_translation = await self.db_session.scalar(select(TourTranslation).where(TourTranslation.id == context.user_data['tour_translation_id']))
        else:
            tour_translation = TourTranslation(language=context.user_data['tour_language'], tour=tour)

        tour_translation.title = update.message.text_markdown_v2_urled
        self.db_session.add(tour_translation)

        tour_section = TourSection(tour_translation=tour_translation, position=0)
        self.db_session.add(tour_section)

        await self.db_session.commit()

        context.user_data['tour_id'] = tour.id
        context.user_data['tour_translation_id'] = tour_translation.id
        context.user_data['tour_section_id'] = tour_section.id

        if is_new_translation:
            await update.message.reply_text(t(user.admin_language).pgettext(
                'admin-tour', "Terrific! Let's add some content now! Send me location, text, photo, audio, video, voice or"
                " video note messages, and send /done when finished with the section."))
            return self.STATE_TOUR_ADD_CONTENT

        await update.message.reply_text(t(user.admin_language).pgettext(
            'admin-tour', "Great! The title was updated."))

        return await self.request_edit_action(self, update, context)

    async def request_edit_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return self.STATE_TOUR_EDIT_SELECT_ACTION

    async def request_tour_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if len(context.application.enabled_languages) == 1:
            context.user_data['tour_language'] = context.application.default_language
            return await self.request_tour_title(update, context)

        user = await self.get_user(update, context)

        await self.edit_or_reply_text(update, context, t(user.admin_language).pgettext(
            'admin-tour', 'Please select the language for the new tour.'),
            reply_markup=self.get_language_select_inline_keyboard(user.admin_language, context, 'tour_language:', True))

        return self.STATE_TOUR_ADD_LANGUAGE

    async def request_tour_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        target_language = None
        if update.callback_query and len(context.matches[0].groups()) == 1:
            target_language = context.matches[0].group(1)
        elif 'tour_language' in context.user_data:
            target_language = context.user_data['tour_language']
            del context.user_data['tour_language']

        if target_language not in context.application.enabled_languages:
            await self.edit_or_reply_text(update, context, t(user.admin_language).pgettext(
                'bot-generic', 'Something went wrong; please try again.'))
            await self.cleanup_context(context)
            return ConversationHandler.END

        context.user_data['tour_language'] = target_language

        await self.edit_or_reply_text(update, context, t(user.admin_language).pgettext('admin-tour', 'Please send me the'
                                                                                       ' title for the tour, or send /cancel to abort.'))

        return self.STATE_TOUR_SAVE_TITLE

    async def select_tour(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        tours = await self.db_session.scalars(select(Tour).options(selectinload(Tour.translation)))
        keyboard = []

        user = await self.get_user(update, context)
        current_language = user.admin_language

        callback_data = update.callback_query.data

        for tour in tours:
            title = get_tour_title(tour, user.admin_language, context)
            keyboard.append([InlineKeyboardButton(title, callback_data='%s:%s' % (callback_data, tour.id))])

        keyboard.append([InlineKeyboardButton(t(current_language).pgettext(
            'bot-generic', 'Abort'), callback_data='cancel')])

        if callback_data == self.CALLBACK_DATA_EDIT_TOUR:
            message = t(current_language).pgettext('admin-tours', 'Please select the tour you want to edit.')
        elif callback_data == self.CALLBACK_DATA_DELETE_TOUR:
            message = t(current_language).pgettext('admin-tours', 'Please select the tour you want to delete.')
        else:
            log.warning(t().pgettext('cli',
                        'Unexpected callback data received in select_tour(): "{0}"').format(callback_data))
            await update.callback_query.edit_message_text(t(user.admin_language).pgettext(
                'bot-generic', 'Something went wrong; please try again.'))
            await self.cleanup_context(context)
            return ConversationHandler.END

        await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

        if callback_data == self.CALLBACK_DATA_EDIT_TOUR:
            return self.STATE_TOUR_EDIT_SELECT_ACTION
        elif callback_data == self.CALLBACK_DATA_DELETE_TOUR:
            return self.STATE_TOUR_DELETE_CONFIRM

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        tours_count = await self.db_session.scalar(select(func.count(Tour.id)))

        if not tours_count:
            await update.message.reply_text(t(user.admin_language).pgettext(
                'admin-tours', "You don't have any tours yet; let's add one!"))
            return await self.request_tour_language(update, context)

        await update.message.reply_text(t(user.admin_language).pgettext(
            'admin-tours', 'I see you have some tours already, what do you want to do?'),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(t(user.admin_language).pgettext('admin-tours',
                                                                         'Add a new one'), callback_data=self.CALLBACK_DATA_ADD_TOUR)
                ],
                [
                    InlineKeyboardButton(t(user.admin_language).pgettext('admin-tours',
                                                                         'Edit an existing tour'), callback_data=self.CALLBACK_DATA_EDIT_TOUR)
                ],
                [
                    InlineKeyboardButton(t(user.admin_language).pgettext('admin-tours',
                                                                         'Delete a tour'), callback_data=self.CALLBACK_DATA_DELETE_TOUR)
                ],
                [
                    InlineKeyboardButton(t(user.admin_language).pgettext(
                        'bot-generic', 'Abort'), callback_data='cancel')
                ],
            ]))

        return self.STATE_SELECT_ACTION
