load all fixtures:
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

migrate docker db:
	docker-compose exec web python manage.py flush --no-input
