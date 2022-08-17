import argparse
import logging
import sys
from venv import create
from tour_guide_bot import log, t, set_fallback_locale
from tour_guide_bot.bot.app import Application
import asyncio
from telegram.ext import PicklePersistence
from sqlalchemy.ext.asyncio import create_async_engine
from os.path import dirname
from os import mkdir, sep


def run():
    parser = argparse.ArgumentParser(
        description=t().pgettext("cli", "Tour Guide bot [telegram]")
    )
    parser.add_argument(
        "--debug",
        "-d",
        help=t().pgettext("cli", "Enable debug logging."),
        action="store_true",
    )
    parser.add_argument(
        "--enabled-languages",
        help=t().pgettext("cli", "Comma-separated list of available languages."),
        default="en",
        type=lambda s: [item.strip() for item in s.split(",")],
    )
    parser.add_argument(
        "--default-language",
        "-l",
        help=t().pgettext(
            "cli",
            "Default language. If not provided, will be set to the first enabled language.",
        ),
        default=None,
        type=str,
    )
    parser.add_argument(
        "--guide-bot-token",
        "-g",
        help=t().pgettext("cli", "Telegram Bot token for the Guide Bot."),
        type=str,
        required=True,
    )
    parser.add_argument(
        "--db",
        help=t().pgettext("cli", "SQLAlchemy engine URL"),
        type=str,
        required=True,
    )

    args = parser.parse_args()

    if len(args.enabled_languages) == 0:
        parser.error(
            t().pgettext("cli", "the list of enabled languages must not be empty")
        )

    if args.default_language is None:
        args.default_language = args.enabled_languages[0]

    if args.default_language not in args.enabled_languages:
        parser.error(
            t().pgettext(
                "cli", "the default language must be in the list of enabled languages"
            )
        )

    set_fallback_locale(args.default_language)

    log.setLevel(logging.INFO)
    if args.debug:
        log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] [%(module)s:%(lineno)d] %(message)s"
        log.setLevel(logging.DEBUG)
    else:
        log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"

    lh = logging.StreamHandler(sys.stdout)
    lh.setFormatter(logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S"))
    log.addHandler(lh)

    engine = create_async_engine(args.db)

    loop = asyncio.get_event_loop()

    app = Application.builder().token(args.guide_bot_token).build()
    app.content_add_lock = asyncio.Lock()
    app.db_engine = engine
    app.enabled_languages = args.enabled_languages
    app.default_language = args.default_language

    parent_path = dirname(dirname(__file__))
    destination_path = parent_path + sep + "persistent"

    try:
        mkdir(destination_path)
    except OSError:
        pass

    app.persistence = PicklePersistence(
        destination_path + sep + "telegram_guide_bot_storage.pickle", update_interval=60
    )

    loop.run_until_complete(app.initialize())
    loop.run_until_complete(app.updater.start_polling())
    loop.run_until_complete(app.start())

    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(app.update_persistence())


if __name__ == "__main__":
    run()
