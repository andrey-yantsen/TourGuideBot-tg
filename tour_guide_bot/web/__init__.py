from aiohttp.web import RouteDef

from . import admin, main

routes = (
    RouteDef(method="GET", path="/", handler=main.index, kwargs={}),
    RouteDef(method="GET", path="/auth", handler=main.auth, kwargs={}),
    RouteDef(method="GET", path="/admin", handler=admin.Index().get, kwargs={}),
)
