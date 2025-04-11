from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django_apscheduler.jobstores import DjangoJobStore
import logging
from booket.utils import complete_old_appointments

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
scheduler.add_jobstore(DjangoJobStore(), "default")


def start():
    scheduler.add_job(
        complete_old_appointments,
        trigger=IntervalTrigger(minutes=10),
        kwargs={"days_back": 0},
        id="appointment_completion_task",
        max_instances=1,
        replace_existing=True,
    )
    logger.info("Started appointment completion scheduler job.")
    scheduler.start()
