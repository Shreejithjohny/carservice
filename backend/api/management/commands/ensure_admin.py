"""
python manage.py ensure_admin

Creates the first admin account from settings, for hosts where you cannot open a shell (e.g. Render's
free plan). Reads ADMIN_EMAIL and ADMIN_PASSWORD. Does nothing when they are not set or the account
already exists: it never changes an existing account or its password.
"""
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from api.models import User, UserRole


class Command(BaseCommand):
    help = "Create the first admin from ADMIN_EMAIL and ADMIN_PASSWORD, if it does not exist yet."

    def handle(self, *args, **options):
        email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("ADMIN_PASSWORD", "")
        if not email or not password:
            return
        if User.objects.filter(email__iexact=email).exists():
            self.stdout.write(f"Admin {email} already exists; left unchanged.")
            return
        user = User(
            email=email,
            username=f"{email.split('@')[0][:100]}_{timezone.now():%M%S%f}"[:150],
            first_name="Admin",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True,
            is_verified=True,
        )
        try:
            validate_password(password, user=user)
        except ValidationError as exc:
            raise CommandError("ADMIN_PASSWORD is too weak: " + " ".join(exc.messages))
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f"Created admin {email}. You can now remove ADMIN_PASSWORD from the settings; the account keeps it."
        ))
