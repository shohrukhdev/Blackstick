###########
# BUILDER #
###########

FROM python:3.12-alpine AS builder

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System deps — compiler tools + WeasyPrint build deps
RUN apk update && apk add --no-cache \
    gcc musl-dev libffi-dev libpq-dev netcat-openbsd gettext \
    pango-dev cairo-dev gdk-pixbuf-dev

RUN pip install --upgrade pip
RUN pip install flake8==7.2.0
COPY . /usr/src/app/
RUN flake8 --ignore=E501,F401 .

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r requirements.txt


#########
# FINAL #
#########

FROM python:3.12-alpine

RUN mkdir -p /home/app
RUN adduser -D -g '' app

ENV HOME=/home/app
ENV APP_HOME=/home/app/web
RUN mkdir $APP_HOME
RUN mkdir $APP_HOME/staticfiles
RUN mkdir $APP_HOME/mediafiles
WORKDIR $APP_HOME

# Runtime deps — WeasyPrint + fonts for PDF generation
RUN apk update && apk add --no-cache \
    netcat-openbsd gettext \
    pango cairo gdk-pixbuf fontconfig ttf-dejavu

COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache /wheels/*

# Copy project (includes entrypoint.sh)
COPY . $APP_HOME

# Fix line endings and permissions for entrypoint
RUN sed -i 's/\r$//g' $APP_HOME/entrypoint.sh && \
    chmod +x $APP_HOME/entrypoint.sh

# Set ownership
RUN chown -R app:app $APP_HOME && \
    chmod -R 755 $APP_HOME/staticfiles && \
    chmod -R 755 $APP_HOME/mediafiles

USER app

ENTRYPOINT ["/home/app/web/entrypoint.sh"]
