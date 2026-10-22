from django.core.management.base import BaseCommand
from django.utils import timezone

from api.reminder_service import send_service_reminders


class Command(BaseCommand):
    help = "Notifies customers whose cars are due or overdue for service. Run once a day (cron / Task Scheduler)."

    def handle(self, *args, **options):
        sent = send_service_reminders(timezone.localdate())
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} service reminder(s)."))
