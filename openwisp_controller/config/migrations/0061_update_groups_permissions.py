from django.db import migrations

from . import assign_permissions_to_groups


class Migration(migrations.Migration):
    dependencies = [
        ("config", "0060_cleanup_api_task_notification_types"),
    ]

    operations = [
        migrations.RunPython(
            assign_permissions_to_groups, reverse_code=migrations.RunPython.noop
        )
    ]
