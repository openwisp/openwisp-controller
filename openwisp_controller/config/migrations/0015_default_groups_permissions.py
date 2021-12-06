import swapper
from django.conf import settings
from django.db import migrations

from . import assign_permissions_to_groups


class Migration(migrations.Migration):
    dependencies = [
        swapper.dependency(
            *swapper.split(settings.AUTH_USER_MODEL), version='0004_default_groups'
        ),
        ('config', '0014_device_hardware_id'),
    ]

    operations = [
        migrations.RunPython(
            assign_permissions_to_groups, reverse_code=migrations.RunPython.noop
        )
    ]
