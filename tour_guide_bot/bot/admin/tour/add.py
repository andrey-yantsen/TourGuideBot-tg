from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tour_guide_bot import t
from tour_guide_bot.bot.admin.tour.add_content import AddContentCommandHandler
from tour_guide_bot.helpers.language_selector import SelectLanguageHandler
from tour_guide_bot.helpers.telegram import SubcommandHandler
from tour_guide_bot.models.guide import Tour, TourSection, TourTranslation


class AddHandler(SubcommandHandler, SelectLanguageHandler, AddContentCommandHandler):
    STATE_TOUR_SAVE_TITLE = 1
    STATE_TOUR_SAVE_DESCRIPTION = 2
    STATE_TOUR_ADD_SECTION = 3
    STATE_TOUR_ADD_CONTENT = 4

    @classmethod
    def get_handlers(cls):
        return [
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        cls.partial(cls.send_language_selector), cls.get_callback_data()
                    ),
                ],
                states={
                    cls.STATE_TOUR_SAVE_TITLE: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.save_tour_title),
                        ),
                    ],
                    cls.STATE_TOUR_SAVE_DESCRIPTION: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.save_tour_translation),
                        ),
                    ],
                    cls.STATE_TOUR_ADD_SECTION: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.tour_add_section),
                        ),
                        CommandHandler("done", cls.partial(cls.tour_add_section_done)),
                    ],
                    cls.STATE_TOUR_ADD_CONTENT: cls.get_add_content_handlers()
                    + [CommandHandler("done", cls.partial(cls.tour_add_content_done))],
                    cls.STATE_LANGUAGE_SELECTION: cls.get_select_language_handlers(),
                },
                fallbacks=[
                    CommandHandler("cancel", cls.partial(cls.cancel)),
                    CallbackQueryHandler(cls.partial(cls.cancel), "cancel"),
                    MessageHandler(filters.COMMAND, cls.partial(cls.unknown_command)),
                    MessageHandler(filters.ALL, cls.partial(cls.unexpected_message)),
                    # add edited message fallback
                ],
                name="admin-add-tour",
                persistent=True,
            )
        ]

    async def after_language_selected(
        self,
        language: str,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        is_single_language: bool,
    ):
        user = await self.get_user(update, context)

        context.user_data["tour_language"] = language

        context.user_data.pop("tour_id", None)
        context.user_data.pop("tour_translation_id", None)
        context.user_data.pop("tour_section_id", None)
        context.user_data.pop("tour_section_position", None)
        context.user_data.pop("tour_section_content_position", None)

        await self.edit_or_reply_text(
            update,
            context,
            t(user.language).pgettext(
                "admin-tour",
                "Please send me the title for the tour, or send /cancel to abort. Do not use any formatting here.",
            ),
        )

        return self.STATE_TOUR_SAVE_TITLE

    async def save_tour_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        context.user_data["tour_title"] = update.message.text

        await update.message.reply_text(
            t(user.language).pgettext(
                "admin-tour",
                "Great! Now send me the description for the tour (or send /cancel to abort). "
                "It will be visible when a user will try to purchase the tour. "
                "You can use formatting here.",
            )
        )
        return self.STATE_TOUR_SAVE_DESCRIPTION

    async def save_tour_translation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        user = await self.get_user(update, context)

        tour = Tour()
        self.db_session.add(tour)

        tour_translation = TourTranslation(
            language=context.user_data["tour_language"], tour=tour
        )

        tour_translation.title = context.user_data["tour_title"]
        tour_translation.description = update.message.text_markdown_v2_urled
        self.db_session.add(tour_translation)

        await self.db_session.commit()

        context.user_data["tour_id"] = tour.id
        context.user_data["tour_translation_id"] = tour_translation.id

        await update.message.reply_text(
            t(user.language).pgettext(
                "admin-tour",
                "Terrific! Let's add some content now! Send me the title for the new section.",
            )
        )
        return self.STATE_TOUR_ADD_SECTION

    async def tour_add_section_done(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)
        await update.message.reply_text(t(language).pgettext("admin-tours", "Done!"))
        return ConversationHandler.END

    async def tour_add_section(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)

        tour_section = TourSection(
            tour_translation_id=context.user_data["tour_translation_id"],
            position=context.user_data.get("tour_section_position", 0),
            title=update.message.text,
        )
        self.db_session.add(tour_section)
        await self.db_session.commit()
        context.user_data["tour_section_id"] = tour_section.id
        context.user_data["tour_section_content_position"] = 0

        await update.message.reply_text(
            t(language).pgettext(
                "admin-tour",
                "Now send me location, text, photo, audio, video, animation, voice or"
                " video note messages, and send /done when finished with the section.",
            )
        )

        return self.STATE_TOUR_ADD_CONTENT

    async def tour_add_content_done(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        user = await self.get_user(update, context)
        tour_section_position = context.user_data.get("tour_section_position", 0)

        if context.user_data.get("action") == "edit_section":
            del context.user_data["action"]
            return ConversationHandler.END

        context.user_data["tour_section_position"] = tour_section_position + 1
        await update.message.reply_text(
            t(user.language).pgettext(
                "admin-tours",
                "Done! Send me the title of the next"
                " tour section, or send /done if you're finished.",
            )
        )
        return self.STATE_TOUR_ADD_SECTION

    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-tour", "Add a tour")

    def get_language_selection_message(self, user_language: str) -> str:
        return t(user_language).pgettext(
            "admin-tour", "Please select the language for the new tour."
        )
