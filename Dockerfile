FROM python:3.10-alpine

RUN apk add build-base libffi-dev libpq-dev mariadb-connector-c-dev curl ffmpeg libogg opus lame
RUN adduser -h /home/tg -D -u 1000 tg
USER tg
WORKDIR /home/tg/app
ENV PATH=/home/tg/.local/bin:$PATH \
    PYTHONUNBUFFERED=1
COPY --chown=tg:tg poetry.lock pyproject.toml /home/tg/app/
RUN curl -sSL https://install.python-poetry.org | python -u - \
  && poetry install --no-dev --no-interaction --no-root
COPY --chown=tg:tg . /home/tg/app/
RUN poetry run pybabel compile --domain=tour_guide_bot --directory=tour_guide_bot/locales
ENTRYPOINT [ "/home/tg/app/docker_entrypoint.sh" ]
