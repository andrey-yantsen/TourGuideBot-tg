import gettext
import logging
import os

log = logging.getLogger(__package__)

__translations = {}
__fallback_locale = "en"


def set_fallback_locale(locale: str) -> None:
    global __fallback_locale
    __fallback_locale = locale


def t(locale: str | None = None) -> gettext.NullTranslations:
    if locale in __translations:
        return __translations[locale]

    if locale is None:
        languages = None
    else:
        languages = [locale, __fallback_locale, "en"]

    __translations[locale] = gettext.translation(
        __package__,
        os.path.dirname(os.path.realpath(__file__)) + "/locales",
        fallback=True,
        languages=languages,
    )

    return __translations[locale]
