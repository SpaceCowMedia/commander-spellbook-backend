###########
# BUILDER #
###########
FROM python:3.14-alpine AS builder

# set work directory
WORKDIR /usr/src/app

# uv build-time configuration; the environment is created at a fixed path so that it
# stays valid when copied into the final image
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# install build dependencies, for packages lacking musl wheels
RUN apk --update add gcc python3-dev libffi-dev musl-dev --no-cache

# install uv
COPY requirements.txt /tmp/requirements.txt
RUN pip install uv -c /tmp/requirements.txt

# install dependencies; the project itself runs from source, so it is not installed
COPY bot/discord/pyproject.toml bot/discord/uv.lock ./
RUN uv sync --locked --no-install-project --no-dev


#########
# BASE  #
#########
FROM python:3.14-alpine AS base

# set environment variables
ENV PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH"

# create the app user
RUN addgroup -S app && adduser -S app -G app

# create the appropriate directories
ENV HOME=/home/app APP_HOME=/home/app/web
WORKDIR $APP_HOME

# install dependencies
COPY --from=builder /opt/venv /opt/venv

# copy project
COPY --chown=app:app bot/discord/ common/ client/python/ $APP_HOME

# change to the app user
USER app

CMD ["python", "spellbook_discord.py"]
