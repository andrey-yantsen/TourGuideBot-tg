import aiohttp_jinja2
from aiohttp.web import Request

from tour_guide_bot.web.admin.base import Base


class Access(Base):
    @aiohttp_jinja2.template("admin/index.html")
    async def get(self, request: Request):
        await self.auth(request)
        return {}
