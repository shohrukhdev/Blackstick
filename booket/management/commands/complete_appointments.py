from django.core.management.base import BaseCommand

from booket.utils import complete_old_appointments


class Command(BaseCommand):
    help = "Mark past appointments as COMPLETED"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days-back",
            type=int,
            default=3,
            help="How many days back to look for appointments (default: 3)",
        )

    def handle(self, *args, **options):
        updated = complete_old_appointments(days_back=options["days_back"])
        self.stdout.write(self.style.SUCCESS(f"Updated {updated} appointment(s) to COMPLETED."))
