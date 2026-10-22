from django.db import migrations


def clear_staff_flag(apps, schema_editor):
    # Permissions now come from the role; a staff flag on a manager/driver/mechanic/customer
    # only exposed the Django admin site and previously made the app treat them as admins.
    User = apps.get_model("api", "User")
    User.objects.filter(is_staff=True, is_superuser=False).exclude(role="ADMIN").update(is_staff=False)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0008_invoice_payments"),
    ]

    operations = [
        migrations.RunPython(clear_staff_flag, migrations.RunPython.noop),
    ]
