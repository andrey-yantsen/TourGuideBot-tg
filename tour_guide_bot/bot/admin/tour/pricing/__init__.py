from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import (
    BaseHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from tour_guide_bot import t
from tour_guide_bot.bot.admin.tour.pricing.add import AddPricingHandler
from tour_guide_bot.bot.admin.tour.pricing.delete import DeletePricingHandler
from tour_guide_bot.bot.admin.tour.pricing.edit import EditPricingHandler
from tour_guide_bot.helpers.telegram import MenuCommandHandler, SubcommandHandler
from tour_guide_bot.models.guide import Tour
from tour_guide_bot.models.settings import PaymentProvider


class PricingMenuHandler(MenuCommandHandler, SubcommandHandler):
    def get_main_menu_unavailable_text(self, language: str) -> str:
        return t(language).pgettext(
            "admin-tour",
            "You need to configure payment providers before you can set up pricing.",
        )

    MENU_ITEMS: list[type[SubcommandHandler]] = [
        AddPricingHandler,
        EditPricingHandler,
        DeletePricingHandler,
    ]

    def get_main_menu_text(self, language: str) -> str:
        return t(language).pgettext("admin-tour", "Please select an action.")

    @staticmethod
    def get_name(language: str) -> str:
        return t(language).pgettext("admin-tour", "Manage pricing")

    async def is_menu_available(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        payment_providers_cnt: int = await self.db_session.scalar(
            select(func.count(PaymentProvider.id)).where(
                PaymentProvider.enabled == True  # noqa
            )
        )

        return await self.is_available(self.db_session) and payment_providers_cnt > 0

    @classmethod
    async def is_available(cls, db_session: AsyncSession) -> bool:
        tours_count: int = await db_session.scalar(select(func.count(Tour.id)))
        return tours_count > 0

    @classmethod
    def get_main_handlers(cls) -> list[BaseHandler]:
        return [
            CallbackQueryHandler(
                cls.partial(cls.main_entrypoint), cls.get_callback_data_pattern()
            ),
        ]
