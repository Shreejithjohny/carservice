from django.db import migrations, models

# Duplicate and legacy role values folded into the five supported roles.
LEGACY_ROLE_MAP = {
    "SERVICE_CENTER": "SERVICE_CENTER_MANAGER",
    "MANAGER": "SERVICE_CENTER_MANAGER",
    "VALET": "DRIVER",
    "EMPLOYEE": "DRIVER",
}
SUPPORTED_ROLES = {"CUSTOMER", "SERVICE_CENTER_MANAGER", "DRIVER", "MECHANIC", "ADMIN"}


def consolidate_roles(apps, schema_editor):
    User = apps.get_model("api", "User")
    for user in User.objects.exclude(role__in=SUPPORTED_ROLES):
        role = (user.role or "").upper()
        role = LEGACY_ROLE_MAP.get(role, role)
        user.role = role if role in SUPPORTED_ROLES else "CUSTOMER"
        user.save(update_fields=["role"])


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0006_alter_invoice_options_and_more"),
    ]

    operations = [
        migrations.RunPython(consolidate_roles, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("CUSTOMER", "Customer"),
                    ("SERVICE_CENTER_MANAGER", "Service Center Manager"),
                    ("DRIVER", "Driver / Valet"),
                    ("MECHANIC", "Mechanic"),
                    ("ADMIN", "Admin"),
                ],
                default="CUSTOMER",
                max_length=30,
            ),
        ),
    ]
