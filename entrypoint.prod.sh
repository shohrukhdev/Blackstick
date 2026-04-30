#!/bin/sh
set -e

echo "==> Running migrations..."
python manage.py migrate --no-input

echo "==> Collecting static files..."
python manage.py collectstatic --no-input \
  --ignore=chartjs --ignore=dist --ignore=dt --ignore=fc --ignore=jui \
  --ignore=login --ignore=node_modules --ignore=plugins --ignore=summernote \
  --ignore=admin --ignore=venv --ignore=rest_framework --ignore=fontawesomefree

echo "==> Compiling translations..."
python manage.py compilemessages -l en
python manage.py compilemessages -l uz
python manage.py compilemessages -l ru

echo "==> Starting server..."
exec "$@"
