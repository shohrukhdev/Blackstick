import threading

from django.apps import AppConfig


class BooketConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'booket'

    def ready(self):
        from booket.utils import complete_old_appointments
        from booket import scheduler

        def run_initial_check():
            import time
            time.sleep(5)   # Let DB connections fully initialize
            complete_old_appointments(days_back=3)

        threading.Thread(target=run_initial_check).start()

        # Start scheduler
        threading.Thread(target=scheduler.start).start()
