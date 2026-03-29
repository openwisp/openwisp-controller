from django.db import migrations

from openwisp_users.migrations import update_admins_permissions


class Migration(migrations.Migration):
    dependencies = [("openwisp_users", "0007_unique_email")]

    operations = [
        migrations.RunPython(
            update_admins_permissions, reverse_code=migrations.RunPython.noop
        )
    ]
