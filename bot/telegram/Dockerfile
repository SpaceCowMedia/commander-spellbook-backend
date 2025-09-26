###########
# BUILDER #
###########
FROM python:3.12-alpine AS builder

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# install dependencies
RUN apk --update add gcc python3-dev libffi-dev musl-dev --no-cache

# pip
RUN pip install --upgrade pip

# install dependencies
COPY bot/telegram/requirements.txt requirements.txt
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/python/wheels -r requirements.txt


#########
# BASE  #
#########
FROM python:3.12-alpine AS base

# create the app user
RUN addgroup -S app && adduser -S app -G app

# create the appropriate directories
ENV HOME=/home/app APP_HOME=/home/app/web
WORKDIR $APP_HOME

# install dependencies
COPY --from=builder /usr/src/app/python/wheels /python/wheels
COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install --no-cache-dir /python/wheels/* --no-deps

# copy project
COPY --chown=app:app bot/telegram/ common/ client/python/ $APP_HOME

# change to the app user
USER app

CMD ["python", "spellbook_telegram.py"]
