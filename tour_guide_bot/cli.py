import argparse
import logging
import sys
from venv import create
from tour_guide_bot import log, t, set_fallback_locale
from tour_guide_bot.admin.app import AdminBot
from tour_guide_bot.guide.app import GuideBot
import asyncio
from telegram.ext import Application
from sqlalchemy.ext.asyncio import create_async_engine


def run():
    parser = argparse.ArgumentParser(description=t().pgettext('cli', 'Tour Guide bot [telegram]'))
    parser.add_argument('--debug', '-d', help=t().pgettext('cli', 'Enable debug logging.'), action='store_true')
    parser.add_argument('--enabled-languages', help=t().pgettext('cli', 'Comma-separated list of available languages.'),
                        default='en', type=lambda s: [item.strip() for item in s.split(',')])
    parser.add_argument('--default-language', '-l', help=t().pgettext('cli',
                        'Default language.'), default='en', type=str)
    parser.add_argument('--guide-bot-token', '-g', help=t().pgettext('cli',
                        'Telegram Bot token for the Guide Bot.'), type=str)
    parser.add_argument('--admin-bot-token', '-a', help=t().pgettext('cli',
                        'Telegram Bot token for the Admin Bot.'), type=str)
    parser.add_argument('--db', help=t().pgettext('cli', 'SQLAlchemy engine URL'), type=str, required=True)

    args = parser.parse_args()

    if not args.guide_bot_token and not args.admin_bot_token:
        parser.error(t().pgettext('cli', 'at least one of --guide-bot-token or --admin-bot-token is required'))

    set_fallback_locale(args.default_language)

    log.setLevel(logging.INFO)
    if args.debug:
        log_format = '[%(asctime)s] [%(levelname)s] [%(name)s] [%(module)s:%(lineno)d] %(message)s'
        log.setLevel(logging.DEBUG)
    else:
        log_format = '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'

    lh = logging.StreamHandler(sys.stdout)
    lh.setFormatter(logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S'))
    log.addHandler(lh)

    engine = create_async_engine(args.db)

    loop = asyncio.get_event_loop()

    async def init_bot(app: Application):
        app.db_engine = engine

        await app.initialize()
        await app.updater.start_polling()
        await app.start()

    if args.admin_bot_token:
        admin_bot = AdminBot.builder().token(args.admin_bot_token).build()
        loop.run_until_complete(init_bot(admin_bot))

    if args.guide_bot_token:
        guide_bot = GuideBot.builder().token(args.guide_bot_token).build()
        loop.run_until_complete(init_bot(guide_bot))

    loop.run_forever()


if __name__ == '__main__':
    run()
