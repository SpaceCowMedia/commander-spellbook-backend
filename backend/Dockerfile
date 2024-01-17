###########
# BUILDER #
###########

# pull official base image
FROM python:3.12.1-alpine as builder

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# install psycopg2 dependencies
RUN apk --update add gcc python3-dev musl-dev postgresql-dev libffi-dev --no-cache

# pip
RUN pip install --upgrade pip

# install dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r requirements.txt


#########
# BASE  #
#########

# pull official base image
FROM python:3.12.1-alpine AS base

# create the app user
RUN addgroup -S app && adduser -S app -G app

# create the appropriate directories
ENV HOME=/home/app APP_HOME=/home/app/web
RUN mkdir -p /home/app && mkdir -p $APP_HOME/staticfiles && chown -R app:app $APP_HOME
WORKDIR $APP_HOME

# install dependencies
RUN \
    apk add --no-cache nginx && \
    mkdir -p /run/nginx && \
    apk --update add libpq --no-cache
COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install --no-cache /wheels/*
RUN pip install --no-cache psycopg[binary] gunicorn

# copy project
COPY --chown=app:app . $APP_HOME

# change to the app user
USER app

# Set environment variables
ARG VERSION=0.0.0
ENV VERSION=${VERSION}
ENV DJANGO_SETTINGS_MODULE=backend.production_settings

# RUN python manage.py collectstatic --no-input --clear
# RUN sleep 3

# run entrypoint.prod.sh
EXPOSE 80
ENTRYPOINT ["/bin/sh", "entrypoint.prod.sh"]
RUN echo -e 'gunicorn backend.wsgi:application --bind 0.0.0.0:8000\n' > entrypoint.prod.sh


#########
# DEMO  #
#########

FROM base AS demo

RUN echo -e 'set -e\n\
python manage.py collectstatic --no-input --clear\n\
sleep 3\n\
python manage.py migrate --noinput\n\
python manage.py clean_jobs\n\
python manage.py export_variants\n\
python manage.py seed_website_properties\n\
gunicorn backend.wsgi:application --bind 0.0.0.0:8000\n' > entrypoint.prod.sh


##############
# PRODUCTION #
##############

FROM base AS production

ADD nginx/production.conf /etc/nginx/nginx.conf

# Switch to user root in order to run nginx on port 80
USER root

RUN echo -e 'python manage.py collectstatic --no-input --clear\n\
nginx\n\
gunicorn backend.wsgi:application --bind 0.0.0.0:8000 --workers=3\n' > entrypoint.prod.sh
