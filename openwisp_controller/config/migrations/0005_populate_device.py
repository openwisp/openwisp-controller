# -*- coding: utf-8 -*-
from django.db import migrations


def forward(apps, schema_editor):
    """
    Creates a Device record for each existing Config
    TODO: delete this migration in future releases
    """
    if not schema_editor.connection.alias == 'default':
        return
    Device = apps.get_model('config', 'Device')
    Config = apps.get_model('config', 'Config')

    for config in Config.objects.all():
        device = Device(
            id=config.id,
            organization=config.organization,
            name=config.name,
            mac_address=config.mac_address,
            key=config.key,
            created=config.created,
            modified=config.modified,
        )
        device.full_clean()
        device.save()
        config.device = device
        config.save()


class Migration(migrations.Migration):
    dependencies = [('config', '0004_add_device_model')]

    operations = [migrations.RunPython(forward, reverse_code=migrations.RunPython.noop)]
