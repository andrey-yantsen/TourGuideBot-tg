from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from tour_guide_bot import t
from tour_guide_bot.bot.guide.tours import ToursCommandHandler
from tour_guide_bot.helpers.telegram import get_tour_title
from tour_guide_bot.helpers.language import LanguageHandler
from telegram import Update
from telegram.ext import ContextTypes, TypeHandler, Application as BaseApplication
from tour_guide_bot.models.guide import BoughtTours, Guest, Tour
from tour_guide_bot.models.telegram import TelegramUser
from .guide.start import StartCommandHandler
from .admin.start import StartCommandHandler as AdminStartCommandHandler
from . import log


class Application(BaseApplication):
    @classmethod
    def builder(cls):
        builder = super().builder()
        builder.application_class(cls)
        return builder

    async def initialize(self) -> None:
        self.add_handler(TypeHandler(object, self.debug_log_handler), -1)

        self.add_handlers(AdminStartCommandHandler.get_handlers())

        self.add_handlers(StartCommandHandler.get_handlers())
        self.add_handlers(ToursCommandHandler.get_handlers())
        self.add_handlers(LanguageHandler.get_handlers())

        self.job_queue.run_repeating(self.check_new_approved_tours, 60, job_kwargs={'misfire_grace_time': 30})

        await super().initialize()

    async def debug_log_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        log.debug('[{0}] received update: {1}'.format(context.application.__class__.__name__, update))

    async def check_new_approved_tours(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        # TODO: Improve the logic
        # Currently this may send an incorrect notification when a guest would have multiple
        # telegram users.
        stmt = select(TelegramUser).join(Guest) \
            .join(BoughtTours, Guest.id == BoughtTours.guest_id) \
            .where(BoughtTours.is_user_notified == False)

        async with AsyncSession(context.application.db_engine, expire_on_commit=False) as session:
            for telegram_user in await session.scalars(stmt):
                stmt = select(BoughtTours).options(selectinload(BoughtTours.tour).selectinload(Tour.translation), selectinload(BoughtTours.guest)) \
                    .where((BoughtTours.guest_id == telegram_user.guest_id) & (BoughtTours.is_user_notified == False))
                bought_tours = await session.scalars(stmt)
                for purchase in bought_tours:
                    language = telegram_user.language

                    await self.bot.send_message(telegram_user.id, t(language).pgettext('guide-bot-notification', 'Hey! You have a new tour available — "{0}".'
                                                                                       ' Send /tours to start the journey!').format(get_tour_title(purchase.tour, language, context)))

                    purchase.is_user_notified = True
                    session.add(purchase)
                    await session.commit()
