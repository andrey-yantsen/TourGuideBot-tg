from datetime import datetime

import aiohttp

CACHE_TTL = 86400


class Currency:
    cache = None
    last_cache_update = None

    @classmethod
    async def ensure_cache(cls) -> None:
        if cls.last_cache_update is not None:
            cache_lifetime = datetime.now() - cls.last_cache_update
            force_cache_update = cache_lifetime.total_seconds() > CACHE_TTL
        else:
            force_cache_update = True

        if force_cache_update:
            await cls.update_cache()

    @staticmethod
    async def load_currencies_config() -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://core.telegram.org/bots/payments/currencies.json"
            ) as response:
                return await response.json()

    @classmethod
    async def update_cache(cls) -> None:
        cls.cache = await cls.load_currencies_config()
        cls.last_cache_update = datetime.now()

    @classmethod
    async def is_known_currency(cls, currency: str) -> bool:
        await cls.ensure_cache()
        return currency in cls.cache

    @classmethod
    async def ensure_currency(cls, currency: str) -> bool:
        await cls.ensure_cache()
        if not await cls.is_known_currency(currency):
            raise ValueError("Unknown currency")

        return cls.cache[currency]

    @classmethod
    async def price_to_telegram(cls, currency: str, price: str) -> int:
        cfg = await cls.ensure_currency(currency)

        price = price.replace(cfg["thousands_sep"], "")
        price = price.replace(cfg["decimal_sep"], ".")
        price = float(price)

        return int(price * pow(10, cfg["exp"]))

    @classmethod
    async def is_valid(cls, currency: str, price: int) -> bool:
        cfg = await cls.ensure_currency(currency)
        return int(cfg["min_amount"]) <= price <= int(cfg["max_amount"])

    @classmethod
    async def price_from_telegram(cls, currency: str, price: int) -> str:
        cfg = await cls.ensure_currency(currency)

        price = str(price)
        ret = ""

        if cfg["exp"] > 0:
            exp = price[-cfg["exp"] :].rjust(cfg["exp"], "0")

            if exp.strip("0"):
                ret = cfg["decimal_sep"] + exp

            price = price[: -cfg["exp"]]

        price_split = []
        while len(price) > 0:
            price_split.append(price[-3:])
            price = price[:-3]
        price_split.reverse()

        if not price_split:
            price_split = ["0"]

        ret = cfg["thousands_sep"].join(price_split) + ret

        if cfg["symbol_left"]:
            if cfg["space_between"]:
                ret = cfg["symbol"] + " " + ret
            else:
                ret = cfg["symbol"] + ret
        else:
            if cfg["space_between"]:
                ret = ret + " " + cfg["symbol"]
            else:
                ret = ret + cfg["symbol"]

        return ret
