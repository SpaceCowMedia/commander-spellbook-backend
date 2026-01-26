##########
# PYTHON #
##########
FROM python:3.12-alpine AS python

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1


###########
# BUILDER #
###########
FROM python AS builder

# set work directory
WORKDIR /usr/src/app

# install dependencies
RUN apk --update add postgresql-dev libffi-dev --no-cache

# install dependencies
COPY backend/requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/python/wheels -r requirements.txt


#########
# BASE  #
#########
FROM python AS base

# create the app user
RUN addgroup -S app && adduser -S app -G app

# create the appropriate directories
ENV HOME=/home/app APP_HOME=/home/app/web
RUN mkdir -p /home/app && mkdir -p $APP_HOME/staticfiles && chown -R app:app $APP_HOME
WORKDIR $APP_HOME

# install dependencies
RUN apk --update add --no-cache libpq
COPY --from=builder /usr/src/app/python/wheels /python-wheels
COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install --no-cache-dir /python-wheels/* --no-deps && rm -rf /python-wheels
RUN pip install --no-cache-dir psycopg[binary] gunicorn

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


##########
# CYTHON #
##########
FROM builder AS cython

RUN pip install --upgrade cython setuptools


##################
# CYTHON-BUILDER #
##################

FROM cython AS cython-builder

COPY backend/ common/ /usr/src/app/
WORKDIR /usr/src/app/
RUN cythonize -i 'spellbook/variants/*.py'


###############
# BASE-CYTHON #
###############
FROM base AS base-cython

COPY --from=cython-builder --parents /usr/src/app/./**/*.so $APP_HOME


#########
# DEMO  #
#########
FROM base-cython AS demo

RUN echo -e 'set -e\n\
python manage.py collectstatic --no-input --clear\n\
sleep 3\n\
python manage.py migrate --noinput\n\
python manage.py seed_website_properties\n\
gunicorn backend.wsgi:application --bind 0.0.0.0:8000' > entrypoint.prod.sh


##############
# PRODUCTION #
##############
FROM base-cython AS production

# Switch to user root in order to run nginx on port 80
USER root

# Install nginx
RUN apk add --no-cache nginx && \
    mkdir -p /run/nginx

ADD backend/nginx/production.conf /etc/nginx/nginx.conf

RUN echo -e 'python manage.py collectstatic --no-input --clear\n\
nginx\n\
gunicorn backend.wsgi:application --bind 0.0.0.0:8000 --workers=3' > entrypoint.prod.sh


##########
# WORKER #
##########
FROM base-cython AS worker

ENV DJANGO_SETTINGS_MODULE=backend.worker_settings

ENTRYPOINT [ "python", "manage.py", "db_worker" ]
