# Tour Guide Bot [telegram]

[![Crowdin](https://badges.crowdin.net/tourguidebot/localized.svg)](https://crowdin.com/project/tourguidebot)

Project allows you to create, manage and share virtual guided tours,
viewable over Telegram.

At this moment you need to manually approve users for your tours using the admin-bot.

# Running

## Preparation

First of all you need to register two bots with [BotFather](https://t.me/BotFather):

1. admin_bot — the bot where you'll be configuring your tours, manage
   generic settings and approve users for the tours.
2. guide_bot — the bot that will be visible for your users, where they'll
   see the tours.

Have the received tokens ready and don't share them anywhere.

## Database

The easiest way to run the bot is by using a sqlite3 database, but it's not
recommended if you expect multiple users at the same time. The example of
how to run the bot with this DB is in the next section.

Keep in mind, that the database connection URL must be in the SQLAlchemy format
see the [documentation](https://docs.sqlalchemy.org/en/14/core/engines.html#database-urls) for further details. Also note that you need to provide
an async dialect for the connection, e.g. aiosqlite or asyncpg.

## Simplest way to run (recommended only for development or testing purposes)

```
$ docker run --restart=unless-stopped -d \
    -v $(pwd)/persistent:/home/tg/app/persistent \
    ghcr.io/andrey-yantsen/tourguidebot-tg:latest \
        -g <telegram_bot_token_guide_bot> \
        -a <telegram_bot_token_admin_bot> \
        --db=sqlite+aiosqlite:////home/tg/app/persistent/tour_guide_bot.sqlite3
```

Do not forget to replace `<telegram_bot_token_guide_bot>` and `<telegram_bot_token_admin_bot>`
with the correct token values.

This command will start a single process for both admin_bot and guide_bot.
This may cause delays in processing requests on high load.

## Recommended way

Copy included `docker-compose.yml.example` into `docker-compose.yml`, and
replace `<telegram_bot_token_guide_bot>` and `<telegram_bot_token_admin_bot>`
with the correct token values.

After that, you should be able to start everything required with the following command:

```
docker-compose up
```
