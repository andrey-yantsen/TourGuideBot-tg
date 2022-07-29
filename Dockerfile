FROM python:3.10-alpine

RUN apk add build-base libpq-dev mariadb-connector-c-dev curl
RUN adduser -h /home/tg -D -u 1000 tg
USER tg
WORKDIR /home/tg/app
ENV PATH=/home/tg/.poetry/bin:$PATH \
    PYTHONUNBUFFERED=1
COPY poetry.lock pyproject.toml /home/tg/app/
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -u - \
  && source $HOME/.poetry/env && poetry install --no-dev --no-interaction --no-root
COPY --chown=tg:tg . /home/tg/app/
RUN poetry run pybabel compile --domain=tour_guide_bot --directory=tour_guide_bot/locales
ENTRYPOINT [ "/home/tg/app/docker_entrypoint.sh" ]
