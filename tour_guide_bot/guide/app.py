from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from tour_guide_bot import t
from tour_guide_bot.guide.tours import ToursCommandHandler
from tour_guide_bot.helpers.telegram import Application, get_tour_title
from tour_guide_bot.helpers.language import LanguageHandler
from telegram.ext import ContextTypes
from tour_guide_bot.models.guest import BoughtTours, Guest
from tour_guide_bot.models.telegram import TelegramUser
from tour_guide_bot.models.tour import Tour
from .start import StartCommandHandler


class GuideBot(Application):
    async def initialize(self) -> None:
        self.add_handlers(StartCommandHandler.get_handlers())
        self.add_handlers(ToursCommandHandler.get_handlers())
        self.add_handlers(LanguageHandler.get_handlers())

        self.job_queue.run_repeating(self.check_new_approved_tours, 60)

        await super().initialize()

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
                    language = self.default_language
                    if purchase.guest.language:
                        language = purchase.guest.language
                    elif telegram_user.language:
                        language = telegram_user.language

                    await self.bot.send_message(telegram_user.id, t(language).pgettext('guide-bot-notification', 'Hey! You have a new your available — "{0}".'
                                                                                       ' Send /tours to start the journey!').format(get_tour_title(purchase.tour, language, context)))

                    purchase.is_user_notified = True
                    session.add(purchase)
                    await session.commit()
