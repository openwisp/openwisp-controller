from django.db import migrations, models


def truncate_failure_reason(apps, schema_editor):
    DeviceConnection = apps.get_model('connection', 'DeviceConnection')

    for device_connection in DeviceConnection.objects.iterator():
        device_connection.failure_reason = device_connection.failure_reason[:128]
        device_connection.save()


class Migration(migrations.Migration):

    dependencies = [('connection', '0004_django3_1_upgrade')]

    operations = [
        migrations.AlterField(
            model_name='deviceconnection',
            name='failure_reason',
            field=models.TextField(blank=True, verbose_name='reason of failure'),
        ),
        migrations.RunPython(migrations.RunPython.noop, truncate_failure_reason),
    ]
