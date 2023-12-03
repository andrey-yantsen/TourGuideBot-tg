FROM python:3.12-alpine AS builder

RUN apk add build-base libffi-dev libpq-dev mariadb-connector-c-dev curl \
  && adduser -h /home/tg -D -u 1000 tg
USER tg
WORKDIR /home/tg/app
ENV PATH=/home/tg/.local/bin:$PATH \
    PYTHONUNBUFFERED=1
COPY --chown=tg:tg poetry.lock pyproject.toml /home/tg/app/
RUN sh <(curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs) -y \
  && curl -sSL https://install.python-poetry.org | python -u - \
  || cat /home/tg/app/poetry-installer-error-* \
  && poetry config virtualenvs.in-project true \
  && poetry install --only main --no-interaction --no-root --no-ansi

FROM python:3.12-alpine
RUN apk add libpq mariadb-connector-c ffmpeg libogg opus lame \
  && adduser -h /home/tg -D -u 1000 tg
USER tg
WORKDIR /home/tg/app
ENV PATH=/home/tg/.local/bin:$PATH \
    PYTHONUNBUFFERED=1
COPY --from=builder /home/tg/app /home/tg/app
COPY --chown=tg:tg . /home/tg/app/
RUN .venv/bin/pybabel compile --domain=tour_guide_bot --directory=tour_guide_bot/locales
ENTRYPOINT [ "/home/tg/app/docker_entrypoint.sh" ]
