from django.db import migrations, models


def remove_conflicting_deviceconnections(apps, schema_editor):
    DeviceConnection = apps.get_model('connection', 'DeviceConnection')
    duplicates = (
        DeviceConnection.objects.values('device_id', 'credentials_id')
        .annotate(count=models.Count('id'))
        .filter(count__gt=1)
    )
    for duplicate in duplicates:
        # Get all instances of this duplicate and order them by oldest to newest
        instances = DeviceConnection.objects.filter(
            device_id=duplicate['device_id'], credentials_id=duplicate['credentials_id']
        ).order_by('created')
        # Keep the old instance and delete the rest
        for instance in instances[1:]:
            instance.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('connection', '0007_command'),
    ]

    operations = [
        migrations.RunPython(
            remove_conflicting_deviceconnections, reverse_code=migrations.RunPython.noop
        ),
    ]
