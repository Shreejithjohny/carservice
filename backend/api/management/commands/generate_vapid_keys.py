from django.core.management.base import BaseCommand

from api.push_service import generate_vapid_keys


class Command(BaseCommand):
    help = "Prints a new key pair for browser push notifications, to paste into backend/.env."

    def handle(self, *args, **options):
        keys = generate_vapid_keys()
        self.stdout.write("Add these lines to backend/.env and restart the backend. Keep the private key secret.\n")
        self.stdout.write(f"VAPID_PUBLIC_KEY={keys['public']}")
        self.stdout.write(f"VAPID_PRIVATE_KEY={keys['private']}")
        self.stdout.write(
            "\nGenerate them only once: new keys make every browser that already enabled alerts stop receiving them."
        )
