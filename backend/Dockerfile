##########
# PYTHON #
##########
FROM python:3.14-alpine AS python

# set environment variables; the uv environment lives at a fixed path so that it stays
# valid when copied between stages
ENV PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH"


###########
# BUILDER #
###########
FROM python AS builder

# set work directory
WORKDIR /usr/src/app

# uv build-time configuration
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# install build dependencies, for packages lacking musl wheels
RUN apk --update add build-base postgresql-dev libffi-dev --no-cache

# install uv
COPY requirements.txt /tmp/requirements.txt
RUN pip install uv -c /tmp/requirements.txt

# install dependencies; the project itself runs from source, so it is not installed
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-install-project --no-dev --group prod


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
COPY --from=builder /opt/venv /opt/venv

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

RUN uv sync --locked --no-install-project --group cython


##################
# CYTHON-BUILDER #
##################

FROM cython AS cython-builder

COPY backend/ common/ /usr/src/app/
WORKDIR /usr/src/app/
# Cython shells out to setuptools, which would try to auto-discover packages from
# pyproject.toml and fail on this multi-package flat layout; only the .so files leave this stage.
RUN rm -f pyproject.toml uv.lock && cythonize -i 'spellbook/variants/*.py'


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
