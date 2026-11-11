"""
python manage.py set_user_role someone@example.com ADMIN

Changes an account's role. Use it to bring back an account of the retired manager role
(as ADMIN, DRIVER, MECHANIC or CUSTOMER), or to make a trusted person an admin.
"""
from django.core.management.base import BaseCommand, CommandError

from api.models import CustomerProfile, User, UserRole

ROLES = [UserRole.CUSTOMER, UserRole.DRIVER, UserRole.MECHANIC, UserRole.ADMIN]


class Command(BaseCommand):
    help = "Change an account's role: CUSTOMER, DRIVER, MECHANIC or ADMIN."

    def add_arguments(self, parser):
        parser.add_argument("email", help="The account's email address")
        parser.add_argument("role", help="CUSTOMER, DRIVER, MECHANIC or ADMIN")

    def handle(self, *args, **options):
        role = options["role"].strip().upper()
        if role not in ROLES:
            raise CommandError(f"Unknown role '{options['role']}'. Use one of: {', '.join(ROLES)}.")
        user = User.objects.filter(email__iexact=options["email"].strip()).first()
        if not user:
            raise CommandError(f"No account uses the email {options['email']}.")

        previous = user.role
        user.role = role
        # A superuser has admin powers whatever the role says, so taking ADMIN away removes that too
        if role != UserRole.ADMIN and user.is_superuser:
            user.is_superuser = False
            user.is_staff = False
        user.save(update_fields=["role", "is_superuser", "is_staff"])
        if role == UserRole.CUSTOMER and not hasattr(user, "customer_profile"):
            CustomerProfile.objects.create(user=user)

        self.stdout.write(self.style.SUCCESS(f"{user.email}: {previous} -> {role}."))
        if role == UserRole.ADMIN:
            self.stdout.write("This person now controls the whole platform: bookings, staff, invoices and refunds.")
        if role in (UserRole.DRIVER, UserRole.MECHANIC) and not hasattr(user, "employee_profile"):
            self.stdout.write("Not linked to a service center yet: bookings can use them at any center until an admin links them.")
        if not user.has_password():
            self.stdout.write("The account has no password. They can sign in with Google, or set one with: python manage.py changepassword " + user.username)
