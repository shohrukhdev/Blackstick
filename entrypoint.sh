#!/bin/sh

python manage.py migrate --no-input

python manage.py collectstatic --no-input \
  --ignore=chartjs --ignore=dist --ignore=dt --ignore=fc \
  --ignore=jui --ignore=login --ignore=node_modules \
  --ignore=plugins --ignore=summernote --ignore=teeth \
  --ignore=admin --ignore=venv --ignore=rest_framework \
  --ignore=fontawesomefree

python manage.py compilemessages -l en
python manage.py compilemessages -l uz
python manage.py compilemessages -l ru

exec "$@"
