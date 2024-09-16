###########
# BUILDER #
###########
FROM python:3.12.6-alpine AS builder

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# install dependencies
RUN echo "@testing https://dl-cdn.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories && \
    apk --update add gcc python3-dev musl-dev postgresql-dev libffi-dev pypy3@testing --no-cache

# pip
RUN pip install --upgrade pip
RUN pypy3 -m ensurepip && pypy3 -m pip install --upgrade pip

# install dependencies
COPY backend/requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/python/wheels -r requirements.txt
RUN pypy3 -m pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/pypy/wheels $(grep -ivE "#|cryptography|cffi" requirements.txt)


#########
# BASE  #
#########
FROM python:3.12.6-alpine AS base

# create the app user
RUN addgroup -S app && adduser -S app -G app

# create the appropriate directories
ENV HOME=/home/app APP_HOME=/home/app/web
RUN mkdir -p /home/app && mkdir -p $APP_HOME/staticfiles && chown -R app:app $APP_HOME
WORKDIR $APP_HOME

# install dependencies
RUN echo "@testing https://dl-cdn.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories && \
    apk add --no-cache nginx pypy3@testing && \
    mkdir -p /run/nginx && \
    apk --update add --no-cache libpq postgresql-dev && \
    ln -s $(which pypy3) $(dirname $(which pypy3))/pypy && \
    pypy -m ensurepip && pypy -m pip install --no-cache-dir --upgrade pip
COPY --from=builder /usr/src/app/python/wheels /python/wheels
COPY --from=builder /usr/src/app/pypy/wheels /pypy/wheels
COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install --no-cache-dir /python/wheels/* --no-deps
RUN pip install --no-cache-dir psycopg[binary] gunicorn
RUN pypy -m pip install --no-cache-dir /pypy/wheels/* --no-deps
RUN pypy -m pip install --no-cache-dir psycopg

# copy project
COPY --chown=app:app backend/ common/ $APP_HOME

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

ADD backend/nginx/production.conf /etc/nginx/nginx.conf

# Switch to user root in order to run nginx on port 80
USER root

RUN echo -e 'python manage.py collectstatic --no-input --clear\n\
nginx\n\
gunicorn backend.wsgi:application --bind 0.0.0.0:8000 --workers=3\n' > entrypoint.prod.sh
