###########
# BUILDER #
###########

# pull official base image
FROM python:3.11.0rc2-alpine as builder

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install psycopg2 dependencies
RUN apk update \
    && apk add gcc python3-dev musl-dev postgresql-dev

# pip
RUN pip install --upgrade pip

# install dependencies
COPY ./requirements.txt .
RUN echo -e "\ngunicorn" >> requirements.txt
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r requirements.txt

# lint
RUN pip install flake8==3.9.2
COPY . .
RUN flake8 --ignore=E501,F401,E128 .


#########
# FINAL #
#########

# pull official base image
FROM python:3.11.0rc2-alpine

# create directory for the app user
RUN mkdir -p /home/app

# create the app user
RUN addgroup -S app && adduser -S app -G app

# create the appropriate directories
ENV HOME=/home/app
ENV APP_HOME=/home/app/web
RUN mkdir $APP_HOME
RUN mkdir $APP_HOME/staticfiles
WORKDIR $APP_HOME

# install dependencies
RUN apk update && apk add libpq glpk
COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install --no-cache /wheels/*

# copy entrypoint.prod.sh
# COPY ./entrypoint.prod.sh .
# RUN sed -i 's/\r$//g'  $APP_HOME/entrypoint.prod.sh
# RUN chmod +x  $APP_HOME/entrypoint.prod.sh

# copy project
COPY . $APP_HOME

# chown all the files to the app user
RUN chown -R app:app $APP_HOME

# change to the app user
USER app

ARG SECRET_KEY
ENV SECRET_KEY=${SECRET_KEY}
ENV DJANGO_SETTINGS_MODULE=backend.production_settings
# run entrypoint.prod.sh
RUN echo "python manage.py collectstatic --no-input --clear" > entrypoint.prod.sh
RUN echo "sleep 3" >> entrypoint.prod.sh
RUN echo "python manage.py migrate --noinput" >> entrypoint.prod.sh
RUN echo "python manage.py clean_jobs" >> entrypoint.prod.sh
RUN echo "python manage.py export_variants" >> entrypoint.prod.sh
RUN echo "gunicorn backend.wsgi:application --bind 0.0.0.0:8000" >> entrypoint.prod.sh
EXPOSE 8000
ENTRYPOINT ["/bin/sh", "entrypoint.prod.sh"]
