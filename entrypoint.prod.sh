#!/bin/sh
set -e

echo "==> Running migrations..."
python manage.py migrate --no-input

echo "==> Collecting static files..."
python manage.py collectstatic --no-input --ignore=teeth

echo "==> Compiling translations..."
python manage.py compilemessages -l en
python manage.py compilemessages -l uz
python manage.py compilemessages -l ru

echo "==> Starting server..."
exec "$@"
