import logging
import gettext
import os
from typing import Optional

log = logging.getLogger('tour_guide_bot')

__translations = {}


def t(locale: Optional[str] = None) -> gettext.NullTranslations:
    if locale in __translations:
        return __translations[locale]

    if locale is None:
        languages = None
    else:
        languages = [locale, 'en']

    __translations[locale] = gettext.translation(__package__, os.path.dirname(
        os.path.realpath(__file__)) + '/locales', languages=languages)

    return __translations[locale]
