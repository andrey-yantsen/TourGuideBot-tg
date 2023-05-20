from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tour_guide_bot import t
from tour_guide_bot.bot.admin import log
from tour_guide_bot.bot.admin.tour.add_content import AddContentCommandHandler
from tour_guide_bot.helpers.currency import Currency
from tour_guide_bot.helpers.telegram import (
    AdminProtectedBaseHandlerCallback,
    get_tour_title,
)
from tour_guide_bot.models.guide import Product, Tour, TourSection, TourTranslation
from tour_guide_bot.models.settings import PaymentProvider


class TourCommandHandler(AdminProtectedBaseHandlerCallback):
    STATE_SELECT_ACTION = 1
    STATE_TOUR_ADD_LANGUAGE = 2
    STATE_TOUR_SAVE_TITLE = 3
    STATE_TOUR_ADD_CONTENT = 4
    STATE_TOUR_EDIT_SELECT_ACTION = 5
    STATE_TOUR_DELETE_CONFIRM = 6
    STATE_TOUR_DELETE = 7
    STATE_TOUR_ADD_SECTION = 8
    STATE_TOUR_EDIT_SELECT_LANGUAGE = 9
    STATE_TOUR_EDIT = 10
    STATE_TOUR_EDIT_PRICE = 10
    STATE_TOUR_EDIT_PRICE_WAITING_CURRENCY = 11
    STATE_TOUR_EDIT_PRICE_WAITING_PRICE = 12
    STATE_TOUR_EDIT_PRICE_WAITING_DURATION = 13

    CALLBACK_DATA_ADD_TOUR = "add_tour"
    CALLBACK_DATA_EDIT_TOUR = "edit_tour"
    CALLBACK_DATA_EDIT_TOUR_PRICE = "edit_tour_price"
    CALLBACK_DATA_DELETE_TOUR = "delete_tour"

    CALLBACK_DATA_TOUR_RENAME = "tour_rename"
    CALLBACK_DATA_TOUR_REMOVE_SECTION = "tour_remove_section"
    CALLBACK_DATA_TOUR_EDIT_SECTION = "edit_section"

    CALLBACK_DATA_DELETE_TOUR_CONFIRMED = "delete_tour_confirmed"

    @classmethod
    def get_handlers(cls):
        return [
            ConversationHandler(
                entry_points=[CommandHandler("tours", cls.partial(cls.start))],
                states={
                    cls.STATE_SELECT_ACTION: [
                        CallbackQueryHandler(
                            cls.partial(cls.request_tour_language),
                            r"^%s$" % (cls.CALLBACK_DATA_ADD_TOUR,),
                        ),
                        CallbackQueryHandler(
                            cls.partial(cls.select_tour),
                            r"^%s$" % (cls.CALLBACK_DATA_EDIT_TOUR,),
                        ),
                        CallbackQueryHandler(
                            cls.partial(cls.select_tour),
                            r"^%s$" % (cls.CALLBACK_DATA_EDIT_TOUR_PRICE,),
                        ),
                        CallbackQueryHandler(
                            cls.partial(cls.select_tour),
                            r"^%s$" % (cls.CALLBACK_DATA_DELETE_TOUR,),
                        ),
                    ],
                    cls.STATE_TOUR_DELETE_CONFIRM: [
                        CallbackQueryHandler(
                            cls.partial(cls.request_delete_tour_confirmation),
                            r"^%s:(\d+)$" % (cls.CALLBACK_DATA_DELETE_TOUR,),
                        ),
                    ],
                    cls.STATE_TOUR_EDIT_SELECT_LANGUAGE: [
                        CallbackQueryHandler(
                            cls.partial(cls.request_tour_language),
                            r"^%s:(\d+)$" % (cls.CALLBACK_DATA_EDIT_TOUR,),
                        ),
                    ],
                    cls.STATE_TOUR_EDIT_SELECT_ACTION: [
                        CallbackQueryHandler(
                            cls.partial(cls.request_edit_action),
                            r"^tour_language:(.+)$",
                        ),
                    ],
                    cls.STATE_TOUR_EDIT: [
                        CallbackQueryHandler(
                            cls.partial(cls.request_tour_title),
                            r"^%s:(\d+)$" % (cls.CALLBACK_DATA_TOUR_RENAME,),
                        ),
                    ],
                    cls.STATE_TOUR_EDIT_PRICE: [
                        CallbackQueryHandler(
                            cls.partial(cls.request_new_price),
                            r"^%s:(\d+)$" % (cls.CALLBACK_DATA_EDIT_TOUR_PRICE,),
                        ),
                    ],
                    cls.STATE_TOUR_EDIT_PRICE_WAITING_CURRENCY: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.save_new_currency),
                        ),
                    ],
                    cls.STATE_TOUR_EDIT_PRICE_WAITING_PRICE: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.save_new_price),
                        ),
                    ],
                    cls.STATE_TOUR_EDIT_PRICE_WAITING_DURATION: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            cls.partial(cls.save_new_duration),
                        ),
                    ],
                    cls.STATE_TOUR_DELETE: [
                        CallbackQueryHandler(
                            cls.partial(cls.delete_tour),
                            r"^%s:(\d+)$" % (cls.CALLBACK_DATA_DELETE_TOUR_CONFIRMED,),
                        ),
                    ],
                    cls.STATE_TOUR_ADD_LANGUAGE: [
                        CallbackQueryHandler(
                            cls.partial(cls.request_tour_title), r"^tour_language:(.*)$"
                        ),
                    ],
                    cls.STATE_TOUR_SAVE_TITLE: [
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
                    cls.STATE_TOUR_ADD_CONTENT: AddContentCommandHandler.get_handlers()
                    + [CommandHandler("done", cls.partial(cls.tour_add_content_done))],
                },
                fallbacks=[
                    CommandHandler("cancel", cls.partial(cls.cancel)),
                    CallbackQueryHandler(cls.partial(cls.cancel), "cancel"),
                    MessageHandler(filters.COMMAND, cls.partial(cls.unknown_command)),
                    MessageHandler(
                        filters.UpdateType.EDITED, cls.partial(cls.edited_message)
                    ),
                ],
                name="admin-tour",
                persistent=True,
            )
        ]

    async def edited_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        language = await self.get_language(update, context)
        await self.reply_text(
            update,
            context,
            t(language).pgettext(
                "admin-tours",
                "Unfortunately, I can't process modifications of the existing messages.",
            ),
        )

    def cleanup_context(self, context: ContextTypes.DEFAULT_TYPE):
        for key in ("tour_language", "tour_id", "action"):
            if key in context.user_data:
                del context.user_data[key]

        self.cleanup_context_tour_translation(context)

    def cleanup_context_tour_translation(self, context: ContextTypes.DEFAULT_TYPE):
        for key in ("tour_translation_id",):
            if key in context.user_data:
                del context.user_data[key]

        self.cleanup_context_tour_translation_section(context)

    def cleanup_context_tour_translation_section(
        self, context: ContextTypes.DEFAULT_TYPE
    ):
        for key in ("tour_section_content_position", "tour_section_position"):
            if key in context.user_data:
                del context.user_data[key]

        self.cleanup_context_audio_conversion(context)

    def cleanup_context_audio_conversion(self, context: ContextTypes.DEFAULT_TYPE):
        for key in (
            "audio_message_id",
            "audio_file_id",
            "audio_caption",
            "voice_file_path",
        ):
            if key in context.user_data:
                del context.user_data[key]

    async def tour_add_section_done(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)
        self.cleanup_context(context)
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

        self.cleanup_context_tour_translation_section(context)

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

    async def delete_tour(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)
        tour = await self.db_session.scalar(
            select(Tour)
            .where(Tour.id == context.matches[0].group(1))
            .options(selectinload(Tour.translation))
        )

        if not tour:
            await self.edit_or_reply_text(
                update,
                context,
                t(user.language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )
            self.cleanup_context(context)
            return ConversationHandler.END

        tour_title = get_tour_title(tour, user.language, context)

        await self.db_session.delete(tour)
        await self.db_session.commit()

        await update.callback_query.edit_message_text(
            t(user.language)
            .pgettext("admin-tours", 'The tour "{0}" was removed.')
            .format(tour_title)
        )
        self.cleanup_context(context)
        return ConversationHandler.END

    async def request_delete_tour_confirmation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        user = await self.get_user(update, context)
        tour = await self.db_session.scalar(
            select(Tour)
            .where(Tour.id == context.matches[0].group(1))
            .options(selectinload(Tour.translation))
        )

        if not tour:
            await self.edit_or_reply_text(
                update,
                context,
                t(user.language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )
            self.cleanup_context(context)
            return ConversationHandler.END

        await update.callback_query.edit_message_text(
            t(user.language)
            .pgettext("admin-tours", 'Do you really want to delete the tour "{0}"?')
            .format(get_tour_title(tour, user.language, context)),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            t(user.language).pgettext("bot-generic", "Yes"),
                            callback_data="%s:%d"
                            % (self.CALLBACK_DATA_DELETE_TOUR_CONFIRMED, tour.id),
                        ),
                        InlineKeyboardButton(
                            t(user.language).pgettext("bot-generic", "Abort"),
                            callback_data="cancel",
                        ),
                    ],
                ]
            ),
        )
        return self.STATE_TOUR_DELETE

    async def save_new_currency(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)
        currency = update.message.text.strip().upper()

        if not await Currency.is_known_currency(currency):
            await update.message.reply_text(
                t(language).pgettext(
                    "admin-tours",
                    "Unknown currency provided. Please try again.",
                )
            )
            return ConversationHandler.WAITING

        context.user_data["currency"] = currency

        await update.message.reply_text(
            t(language)
            .pgettext(
                "admin-tours",
                "Please send me the price of the tour in {}.",
            )
            .format(currency)
        )

        return self.STATE_TOUR_EDIT_PRICE_WAITING_PRICE

    async def save_new_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        language = await self.get_language(update, context)
        price = update.message.text.strip()

        currency = context.user_data["currency"]

        try:
            price = await Currency.price_to_telegram(currency, price)
        except ValueError:
            price = None

        if not price or not await Currency.is_valid(currency, price):
            await update.message.reply_text(
                t(language).pgettext(
                    "admin-tours",
                    "Invalid value provided, please try again.",
                )
            )
            return ConversationHandler.WAITING

        context.user_data["price"] = price

        await update.message.reply_text(
            t(language)
            .pgettext(
                "admin-tours",
                "How long (in days) {} should buy?",
            )
            .format(await Currency.price_from_telegram(currency, price))
        )

        return self.STATE_TOUR_EDIT_PRICE_WAITING_DURATION

    async def save_new_duration(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)
        duration = update.message.text.strip()

        try:
            duration = int(duration)
        except ValueError:
            duration = None

        if not duration:
            await update.message.reply_text(
                t(language).pgettext(
                    "admin-tours",
                    "Invalid value provided, please try again.",
                )
            )
            self.cleanup_context(context)
            return ConversationHandler.WAITING

        currency = context.user_data["currency"]
        price = context.user_data["price"]

        tour = await self.db_session.scalar(
            select(Tour)
            .where(Tour.id == context.user_data["tour_id"])
            .options(selectinload(Tour.translation))
        )

        product = await self.db_session.scalar(
            select(Product).where((Product.tour == tour) & (Product.available == True))
        )

        if product:
            product.available = False
            self.db_session.add(product)

        payment_provider = await self.db_session.scalar(
            select(PaymentProvider).where(PaymentProvider.enabled == True)
        )

        if not payment_provider:
            await self.edit_or_reply_text(
                update,
                context,
                t(language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )
            self.cleanup_context(context)
            return ConversationHandler.END

        product = Product(
            tour=tour,
            currency=currency,
            price=price,
            duration_days=duration,
            payment_provider=payment_provider,
        )

        self.db_session.add(product)
        await self.db_session.commit()

        await update.message.reply_text(
            t(language)
            .npgettext(
                "admin-tours",
                "From now on users can buy {}-day access to {} for {}.",
                "From now on users can buy {}-days access to {} for {}.",
                product.duration_days,
            )
            .format(
                product.duration_days,
                get_tour_title(tour, language, context),
                await Currency.price_from_telegram(currency, price),
            )
        )

        return ConversationHandler.END

    async def request_new_price(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        user = await self.get_user(update, context)
        tour = await self.db_session.scalar(
            select(Tour)
            .where(Tour.id == context.matches[0].group(1))
            .options(selectinload(Tour.translation), selectinload(Tour.products))
        )

        if not tour:
            await self.edit_or_reply_text(
                update,
                context,
                t(user.language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )
            self.cleanup_context(context)
            return ConversationHandler.END

        context.user_data["tour_id"] = tour.id

        available_products = [product for product in tour.products if product.available]

        await update.callback_query.answer()
        if available_products:
            product = available_products[0]
            msg = (
                t(user.language)
                .npgettext(
                    "admin-tours",
                    r"Current price is {} for {} day\.",
                    r"Current price is {} for {} days\.",
                    product.duration_days,
                )
                .format(
                    await Currency.price_from_telegram(product.currency, product.price),
                    product.duration_days,
                )
            )

            msg += " " + t(user.language).pgettext(
                "admin-tours",
                r"Please send me the currency for the new price, or /cancel to abort\.",
            )
        else:
            msg = t(user.language).pgettext(
                "admin-tours",
                r"Please send me the currency in which you want to charge your users, or /cancel to abort\.",
            )

        msg += "\n\n" + t(user.language).pgettext(
            "admin-tours",
            r"You can find more details about available currencies [here](https://core.telegram.org/bots/payments#supported-currencies)\.",
        )

        await update.callback_query.edit_message_text(
            msg,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True,
        )
        return self.STATE_TOUR_EDIT_PRICE_WAITING_CURRENCY

    async def save_tour_translation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        user = await self.get_user(update, context)

        if "tour_id" in context.user_data:
            tour = await self.db_session.scalar(
                select(Tour).where(Tour.id == context.user_data["tour_id"])
            )
        else:
            tour = Tour()
            self.db_session.add(tour)

        is_new_translation = True
        if "tour_translation_id" in context.user_data:
            is_new_translation = False
            tour_translation = await self.db_session.scalar(
                select(TourTranslation).where(
                    TourTranslation.id == context.user_data["tour_translation_id"]
                )
            )
        else:
            tour_translation = TourTranslation(
                language=context.user_data["tour_language"], tour=tour
            )

        tour_translation.title = update.message.text_markdown_v2_urled
        self.db_session.add(tour_translation)

        await self.db_session.commit()

        context.user_data["tour_id"] = tour.id
        context.user_data["tour_translation_id"] = tour_translation.id

        if is_new_translation:
            await update.message.reply_text(
                t(user.language).pgettext(
                    "admin-tour",
                    "Terrific! Let's add some content now! Send me the title for the new section.",
                )
            )
            return self.STATE_TOUR_ADD_SECTION

        await update.message.reply_text(
            t(user.language).pgettext("admin-tour", "Great! The title was updated.")
        )

        return await self.request_edit_action(update, context)

    async def request_edit_action(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)

        if (
            update.callback_query
            and len(context.matches[0].groups()) == 1
            and update.callback_query.data.startswith("tour_language")
        ):
            target_language = context.matches[0].group(1)
        elif "tour_language" in context.user_data:
            target_language = context.user_data["tour_language"]
            del context.user_data["tour_language"]

        if target_language not in context.application.enabled_languages:
            await self.edit_or_reply_text(
                update,
                context,
                t(language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )
            self.cleanup_context(context)
            return ConversationHandler.END

        context.user_data["tour_language"] = target_language

        if update.callback_query:
            await update.callback_query.answer()

        tour_translation = await self.db_session.scalar(
            select(TourTranslation).where(
                (TourTranslation.tour_id == context.user_data["tour_id"])
                & (TourTranslation.language == target_language)
            )
        )

        if tour_translation:
            context.user_data["tour_translation_id"] = tour_translation.id
        else:
            await self.edit_or_reply_text(
                update,
                context,
                t(language).pgettext(
                    "admin-tour",
                    "The tour doesn't have a translation to the selected language. Let's add one then!"
                    " Please send me the title.",
                ),
            )
            return self.STATE_TOUR_SAVE_TITLE

        await self.edit_or_reply_text(
            update,
            context,
            t(language).pgettext("admin-tour", "Please select the action."),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            t(language).pgettext("admin-tour", "Rename"),
                            callback_data="%s:%d"
                            % (
                                self.CALLBACK_DATA_TOUR_RENAME,
                                context.user_data["tour_id"],
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            t(language).pgettext("admin-tour", "Remove a section"),
                            callback_data="%s:%d"
                            % (
                                self.CALLBACK_DATA_TOUR_REMOVE_SECTION,
                                context.user_data["tour_id"],
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            t(language).pgettext("admin-tour", "Edit a section"),
                            callback_data="%s:%d"
                            % (
                                self.CALLBACK_DATA_TOUR_EDIT_SECTION,
                                context.user_data["tour_id"],
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            t(language).pgettext("bot-generic", "Abort"),
                            callback_data="cancel",
                        )
                    ],
                ]
            ),
        )

        return self.STATE_TOUR_EDIT

    async def request_tour_language(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        language = await self.get_language(update, context)

        if update.callback_query and update.callback_query.data.startswith(
            self.CALLBACK_DATA_EDIT_TOUR + ":"
        ):
            context.user_data["action"] = "edit"
            context.user_data["tour_id"] = int(context.matches[0].group(1))

            if len(context.application.enabled_languages) == 1:
                context.user_data[
                    "tour_language"
                ] = context.application.default_language
                return await self.request_edit_action(update, context)

            message = t(language).pgettext(
                "admin-tour", "Please select the language you want to update."
            )

        if len(context.application.enabled_languages) == 1:
            context.user_data["tour_language"] = context.application.default_language
            return await self.request_tour_title(update, context)
        else:
            message = t(language).pgettext(
                "admin-tour", "Please select the language for the new tour."
            )

        if update.callback_query:
            await update.callback_query.answer()

        user = await self.get_user(update, context)

        await self.edit_or_reply_text(
            update,
            context,
            message,
            reply_markup=self.get_language_select_inline_keyboard(
                user.language, context, "tour_language:", True
            ),
        )

        if context.user_data.get("action") == "edit":
            return self.STATE_TOUR_EDIT_SELECT_ACTION

        return self.STATE_TOUR_ADD_LANGUAGE

    async def request_tour_title(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        user = await self.get_user(update, context)

        target_language = None
        if (
            update.callback_query
            and update.callback_query.data.startswith("tour_language:")
            and len(context.matches[0].groups()) == 1
        ):
            target_language = context.matches[0].group(1)
        elif "tour_language" in context.user_data:
            target_language = context.user_data["tour_language"]
            del context.user_data["tour_language"]

        if update.callback_query and update.callback_query.data.startswith(
            self.CALLBACK_DATA_TOUR_RENAME + ":"
        ):
            context.user_data["tour_id"] = int(context.matches[0].group(1))

        if update.callback_query:
            await update.callback_query.answer()

        if target_language not in context.application.enabled_languages:
            await self.edit_or_reply_text(
                update,
                context,
                t(user.language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                ),
            )
            self.cleanup_context(context)
            return ConversationHandler.END

        context.user_data["tour_language"] = target_language

        await self.edit_or_reply_text(
            update,
            context,
            t(user.language).pgettext(
                "admin-tour",
                "Please send me the title for the tour, or send /cancel to abort.",
            ),
        )

        return self.STATE_TOUR_SAVE_TITLE

    async def select_tour(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        tours = await self.db_session.scalars(
            select(Tour).options(selectinload(Tour.translation))
        )
        keyboard = []

        user = await self.get_user(update, context)
        current_language = user.language

        callback_data = update.callback_query.data

        for tour in tours:
            title = get_tour_title(tour, user.language, context)
            keyboard.append(
                [
                    InlineKeyboardButton(
                        title, callback_data="%s:%s" % (callback_data, tour.id)
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    t(current_language).pgettext("bot-generic", "Abort"),
                    callback_data="cancel",
                )
            ]
        )

        if callback_data == self.CALLBACK_DATA_EDIT_TOUR:
            message = t(current_language).pgettext(
                "admin-tours", "Please select the tour you want to edit."
            )
        elif callback_data == self.CALLBACK_DATA_DELETE_TOUR:
            message = t(current_language).pgettext(
                "admin-tours", "Please select the tour you want to delete."
            )
        elif callback_data == self.CALLBACK_DATA_EDIT_TOUR_PRICE:
            message = t(current_language).pgettext(
                "admin-tours", "Please select the tour for updating the price."
            )
        else:
            log.warning(
                t()
                .pgettext(
                    "cli", 'Unexpected callback data received in select_tour(): "{0}"'
                )
                .format(callback_data)
            )
            await update.callback_query.edit_message_text(
                t(user.language).pgettext(
                    "bot-generic", "Something went wrong; please try again."
                )
            )
            self.cleanup_context(context)
            return ConversationHandler.END

        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            message, reply_markup=InlineKeyboardMarkup(keyboard)
        )

        if callback_data == self.CALLBACK_DATA_EDIT_TOUR:
            return self.STATE_TOUR_EDIT_SELECT_LANGUAGE
        elif callback_data == self.CALLBACK_DATA_DELETE_TOUR:
            return self.STATE_TOUR_DELETE_CONFIRM
        elif callback_data == self.CALLBACK_DATA_EDIT_TOUR_PRICE:
            return self.STATE_TOUR_EDIT_PRICE

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await self.get_user(update, context)

        tours_count = await self.db_session.scalar(select(func.count(Tour.id)))

        if not tours_count:
            await update.message.reply_text(
                t(user.language).pgettext(
                    "admin-tours", "You don't have any tours yet; let's add one!"
                )
            )
            return await self.request_tour_language(update, context)

        await update.message.reply_text(
            t(user.language).pgettext(
                "admin-tours",
                "I see you have some tours already, what do you want to do?",
            ),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            t(user.language).pgettext("admin-tours", "Add a new one"),
                            callback_data=self.CALLBACK_DATA_ADD_TOUR,
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            t(user.language).pgettext(
                                "admin-tours", "Set/change tour price"
                            ),
                            callback_data=self.CALLBACK_DATA_EDIT_TOUR_PRICE,
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            t(user.language).pgettext(
                                "admin-tours", "Edit an existing tour"
                            ),
                            callback_data=self.CALLBACK_DATA_EDIT_TOUR,
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            t(user.language).pgettext("admin-tours", "Delete a tour"),
                            callback_data=self.CALLBACK_DATA_DELETE_TOUR,
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            t(user.language).pgettext("bot-generic", "Abort"),
                            callback_data="cancel",
                        )
                    ],
                ]
            ),
        )

        return self.STATE_SELECT_ACTION
