from aiohttp.web import Request, Response

from tour_guide_bot.web.admin.base import Base


class Index(Base):
    async def get(self, request: Request):
        await self.auth(request)
        return Response(text="admin")
