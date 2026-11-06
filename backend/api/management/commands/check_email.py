"""
python manage.py check_email you@example.com

Shows the email settings Django actually loaded (never the password), sends a test email, and
explains the usual reasons it fails. Use it when sign-in codes don't arrive by email.
"""
import smtplib
import socket
import ssl

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


def explain(exc):
    """A plain-language fix for the usual SMTP failures."""
    text = str(exc)
    host = settings.EMAIL_HOST.lower()
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        if "gmail" in host or "google" in host:
            return ("Gmail refused the login. EMAIL_HOST_PASSWORD must be a 16-letter App Password "
                    "(Google Account > Security > 2-Step Verification > App passwords), not your normal "
                    "password, and EMAIL_HOST_USER must be the same Gmail address the App Password belongs to.")
        return "The mail server refused the username/password. Check EMAIL_HOST_USER and EMAIL_HOST_PASSWORD."
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return (f"The server would not send From {settings.DEFAULT_FROM_EMAIL!r}. Set DEFAULT_FROM_EMAIL to your "
                "login address or a sender you verified with your email provider.")
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "The server refused the recipient address. Check it for typos."
    if isinstance(exc, smtplib.SMTPNotSupportedError) or "STARTTLS" in text:
        return "This server/port doesn't support STARTTLS. For port 465 set EMAIL_USE_SSL=True; otherwise use port 587."
    if isinstance(exc, ssl.SSLError):
        return ("TLS/SSL mismatch: use EMAIL_PORT=587 with EMAIL_USE_TLS=True, or EMAIL_PORT=465 with "
                "EMAIL_USE_SSL=True (port 465 now selects SSL automatically).")
    if isinstance(exc, socket.gaierror):
        return f"The mail server name {settings.EMAIL_HOST!r} could not be found. Check EMAIL_HOST for typos."
    if isinstance(exc, (ConnectionRefusedError, TimeoutError, socket.timeout)) or "timed out" in text:
        return (f"Could not connect to {settings.EMAIL_HOST}:{settings.EMAIL_PORT}. Check EMAIL_HOST/EMAIL_PORT; "
                "some hosting providers and networks block outgoing mail ports (try 587, or 2525 if your "
                "provider offers it).")
    if isinstance(exc, smtplib.SMTPServerDisconnected):
        return "The server closed the connection. Usually a wrong port or TLS/SSL setting (see EMAIL_PORT)."
    return "Unexpected error; the message above comes straight from the mail server."


class Command(BaseCommand):
    help = "Send a test email with the current EMAIL_* settings and explain any failure."

    def add_arguments(self, parser):
        parser.add_argument("to", help="Address to send the test email to")

    def handle(self, *args, **options):
        to = options["to"]
        self.stdout.write("Email settings Django loaded (from backend/.env or the environment):")
        self.stdout.write(f"  EMAIL_HOST          = {settings.EMAIL_HOST!r}")
        self.stdout.write(f"  EMAIL_PORT          = {settings.EMAIL_PORT}")
        self.stdout.write(f"  EMAIL_USE_TLS       = {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"  EMAIL_USE_SSL       = {getattr(settings, 'EMAIL_USE_SSL', False)}")
        self.stdout.write(f"  EMAIL_HOST_USER     = {settings.EMAIL_HOST_USER!r}")
        self.stdout.write(f"  EMAIL_HOST_PASSWORD = {'set (' + str(len(settings.EMAIL_HOST_PASSWORD)) + ' characters)' if settings.EMAIL_HOST_PASSWORD else 'NOT SET'}")
        self.stdout.write(f"  DEFAULT_FROM_EMAIL  = {settings.DEFAULT_FROM_EMAIL!r}")

        if not settings.EMAIL_HOST:
            raise CommandError(
                "EMAIL_HOST is empty, so sign-in codes are only printed in the backend terminal. Put the EMAIL_* "
                "settings in backend/.env (the folder with manage.py, not the project root) and restart the server."
            )
        if "gmail" in settings.EMAIL_HOST.lower() and len(settings.EMAIL_HOST_PASSWORD) != 16:
            self.stdout.write(self.style.WARNING(
                "  Note: Gmail App Passwords are 16 letters. This one isn't, so it is probably your normal "
                "password, which Gmail will refuse."
            ))

        self.stdout.write(f"\nSending a test email to {to} ...")
        try:
            send_mail(
                "Smart Doorstep Vehicle Service - test email",
                "If you can read this, sign-in codes can be delivered by email.",
                settings.DEFAULT_FROM_EMAIL,
                [to],
                fail_silently=False,
            )
        except Exception as exc:  # noqa: BLE001 - every failure gets explained
            raise CommandError(f"Sending failed: {type(exc).__name__}: {exc}\nLikely fix: {explain(exc)}")
        self.stdout.write(self.style.SUCCESS(
            f"Sent. If it isn't in {to}'s inbox within a minute, check Spam/Promotions/All Mail."
        ))
