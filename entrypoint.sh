#!/bin/sh

python manage.py migrate
python manage.py collectstatic --no-input --ignore=chartjs --ignore=dist --ignore=dt --ignore=fc --ignore=jui --ignore=login --ignore=node_modules --ignore=plugins --ignore=summernote --ignore=teeth --ignore=admin --ignore=venv --ignore=rest_framework --ignore=fontawesomefree -v 2
python manage.py compilemessages -l en
python manage.py compilemessages -l uz
python manage.py compilemessages -l ru

python manage.py loaddata users.json
python manage.py loaddata roles.json
python manage.py loaddata clinics.json
python manage.py loaddata staff.json
python manage.py loaddata patients.json
python manage.py loaddata categories.json
python manage.py loaddata procedures.json
python manage.py loaddata proceduretoothstates.json
python manage.py loaddata services.json
python manage.py loaddata servicestaff.json
python manage.py loaddata teeth.json
python manage.py loaddata toothstates.json
python manage.py loaddata treatment.json

python manage.py loaddata providers.json
python manage.py loaddata service_types.json
python manage.py loaddata servers.json
python manage.py loaddata services.json
python manage.py loaddata provider_server.json
python manage.py loaddata provider_server_services.json
python manage.py loaddata clients.json
python manage.py loaddata provider_clients.json
python manage.py loaddata appointments.json
python manage.py loaddata appointment_services.json

exec "$@"