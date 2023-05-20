from datetime import datetime, timedelta

import pytest

from tests.conftest import get_currency_config
from tour_guide_bot.helpers.currency import Currency


@pytest.mark.usefixtures("mock_currency_config")
async def test_config_loading():
    await Currency.ensure_cache()

    assert Currency.cache == await get_currency_config()


@pytest.mark.usefixtures("mock_currency_config")
async def test_cache_expiration():
    await Currency.ensure_cache()
    assert Currency.last_cache_update is not None
    assert datetime.now() - Currency.last_cache_update < timedelta(days=1)

    old_last_cache_update = Currency.last_cache_update
    await Currency.ensure_cache()
    assert old_last_cache_update == Currency.last_cache_update

    Currency.last_cache_update = datetime.now() - timedelta(days=10)
    await Currency.ensure_cache()

    assert datetime.now() - Currency.last_cache_update < timedelta(days=1)


async def test_load_real_config():
    Currency.cache = None
    Currency.last_cache_update = None
    await Currency.ensure_cache()
    assert Currency.cache is not None
    assert len(Currency.cache) > 0


@pytest.mark.usefixtures("mock_currency_config")
async def test_ensure_currency_known():
    await Currency.ensure_currency("USD")


@pytest.mark.usefixtures("mock_currency_config")
async def test_ensure_currency_unknown():
    with pytest.raises(ValueError):
        await Currency.ensure_currency("BTC")


@pytest.mark.usefixtures("mock_currency_config")
async def test_price_to_telegram_conversion():
    assert await Currency.price_to_telegram("USD", "100") == 10000
    assert await Currency.price_to_telegram("USD", "100.00") == 10000
    assert await Currency.price_to_telegram("USD", "1,000.00") == 100000

    assert await Currency.price_to_telegram("CLP", "1000") == 1000
    assert await Currency.price_to_telegram("CLP", "1.000") == 1000


@pytest.mark.usefixtures("mock_currency_config")
async def test_price_valid():
    assert await Currency.is_valid("USD", 100)
    assert not await Currency.is_valid("USD", 0)
    assert not await Currency.is_valid("USD", -100)
    assert not await Currency.is_valid("USD", 5_000_000)


@pytest.mark.usefixtures("mock_currency_config")
async def test_price_from_telegram_conversion():
    assert await Currency.price_from_telegram("USD", 100) == "$1"
    assert await Currency.price_from_telegram("USD", 100000) == "$1,000"
    assert await Currency.price_from_telegram("USD", 123) == "$1.23"
    assert await Currency.price_from_telegram("USD", 100045) == "$1,000.45"

    assert await Currency.price_from_telegram("AED", 100) == "AED 1"
    assert await Currency.price_from_telegram("AED", 100000) == "AED 1,000"
    assert await Currency.price_from_telegram("AED", 123) == "AED 1.23"
    assert await Currency.price_from_telegram("AED", 100045) == "AED 1,000.45"

    assert await Currency.price_from_telegram("CLP", 100) == "100 CLP"
    assert await Currency.price_from_telegram("CLP", 100000) == "100.000 CLP"
    assert await Currency.price_from_telegram("CLP", 123) == "123 CLP"
    assert await Currency.price_from_telegram("CLP", 100045) == "100.045 CLP"

    assert await Currency.price_from_telegram("XXX", 100) == "100XXX"
    assert await Currency.price_from_telegram("XXX", 100000) == "100.000XXX"
    assert await Currency.price_from_telegram("XXX", 123) == "123XXX"
    assert await Currency.price_from_telegram("XXX", 100045) == "100.045XXX"
