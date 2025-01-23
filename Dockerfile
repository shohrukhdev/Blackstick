###########
# BUILDER #
###########

# pull official base image
FROM python:3.12-alpine as builder

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install system dependencies
RUN apk update && \
    apk add --no-cache gcc musl-dev libffi-dev libpq-dev netcat-openbsd gettext

# lint
RUN pip install --upgrade pip
RUN pip install flake8==7.1.1
COPY .. /usr/src/app/
RUN flake8 --ignore=E501,F401 .

# install python dependencies
COPY ../requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r requirements.txt


#########
# FINAL #
#########

# pull official base image
FROM python:3.12-alpine

# create directory for the app user
RUN mkdir -p /home/app

# Create the app user (using Alpine's syntax for adduser)
RUN adduser -D -g '' app

# create the appropriate directories
ENV HOME=/home/app
ENV APP_HOME=/home/app/web
RUN mkdir $APP_HOME
RUN mkdir $APP_HOME/staticfiles
RUN mkdir $APP_HOME/mediafiles
WORKDIR $APP_HOME

# Install dependencies using apk (Alpine's package manager)
RUN apk update && apk add --no-cache netcat-openbsd gettext

COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache /wheels/*

# copy entrypoint.sh
COPY entrypoint.sh .
RUN sed -i 's/\r$//g'  $APP_HOME/entrypoint.sh
RUN chmod +x  $APP_HOME/entrypoint.sh

# copy project
COPY .. $APP_HOME

# chown all the files to the app user
RUN chown -R app:app $APP_HOME

# change to the app user
USER app

# run entrypoint.sh
ENTRYPOINT ["/home/app/web/entrypoint.sh"]