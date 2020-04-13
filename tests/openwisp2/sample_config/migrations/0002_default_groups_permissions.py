from django.db import migrations
from django.contrib.auth.models import Permission

from openwisp_controller.config.migrations import assign_permissions_to_groups


class Migration(migrations.Migration):
    dependencies = [
        ('sample_config', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            assign_permissions_to_groups, reverse_code=migrations.RunPython.noop
        ),
    ]
