# Tour Guide Bot [telegram]

[![Crowdin](https://badges.crowdin.net/tourguidebot/localized.svg)](https://crowdin.com/project/tourguidebot)

Project allows you to create, manage and share virtual guided tours,
viewable over Telegram.

At this moment you need to manually approve users for your tours using the
admin-mode in the bot.

# Bot commands

## Guide mode (default)

* `/start` — initialize the bot. It will greet you, ask for the phone number
             and check if you have any tours approved.
* `/tours` — list the available tours and start one of them.
* `/language` - change the interface language.
* `/admin` — switch to the admin mode.

## Admin mode

* `/guest` — exit the admin mode.
* `/language` - change the interface language.
* `/configure` — change the bot's settings.
* `/tours` — manage your tours.
* `/approve` — allow somebody to access a tour.
* `/revoke` — revoke access to a tour.

# Running

## Preparation

First of all you need to register a bot with [BotFather](https://t.me/BotFather).

Have the received token ready and don't share it anywhere.

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
        -g <telegram_bot_token> \
        --db=sqlite+aiosqlite:////home/tg/app/persistent/tour_guide_bot.sqlite3
```

Do not forget to replace `<telegram_bot_token>` with the correct token value.

This command will start a single process for both admin_bot and guide_bot.
This may cause delays in processing requests on high load.

## Recommended way

Copy included `docker-compose.yml.example` into `docker-compose.yml`, and
replace `<telegram_bot_token>` with the correct token value.

After that, you should be able to start everything required with the following
command:

```
docker-compose up
```
