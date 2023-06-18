import hmac
from hashlib import sha256
from time import time

import aiohttp_jinja2
import aiohttp_session
from aiohttp.web import HTTPForbidden, HTTPTemporaryRedirect, Request

from tour_guide_bot import t


@aiohttp_jinja2.template("index.html")
async def index(request: Request):
    session = await aiohttp_session.get_session(request)
    if "user_info" in session:
        raise HTTPTemporaryRedirect(location="/admin")

    return {
        "hostname": request.host,
        "scheme": request.headers.get("X-Forwarded-Proto", request.scheme),
    }


async def auth(request: Request):
    data_check_list = []

    hash = request.query.get("hash")
    for key, value in sorted(request.query.items(), key=lambda x: x[0]):
        if key != "hash":
            data_check_list.append(f"{key}={value}")

    secret_key = sha256(request.app.bot.token.encode("ascii")).digest()
    hash_check = (
        hmac.new(secret_key, "\n".join(data_check_list).encode("ascii"), sha256)
        .hexdigest()
        .lower()
    )

    if hash != hash_check:
        raise HTTPForbidden(
            text=t(request.app.default_language).pgettext("web-auth", "Invalid hash")
        )

    if time() - int(request.query.get("auth_date", 0)) > 900:
        raise HTTPForbidden(
            text=t(request.app.default_language).pgettext("web-auth", "Data is too old")
        )

    session = await aiohttp_session.get_session(request)
    session["user_info"] = {
        "id": request.query.get("id"),
        "first_name": request.query.get("first_name"),
        "last_name": request.query.get("last_name"),
        "username": request.query.get("username"),
        "photo_url": request.query.get("photo_url"),
    }

    raise HTTPTemporaryRedirect(location="/admin")
