import model_utils.fields
from django.db import migrations, models


def migrate_last_ip_forward(apps, schema_editor):
    device_model = apps.get_model('config', 'Device')
    devices = device_model.objects.all().select_related('config')
    for device in devices:
        if not hasattr(device, 'config'):
            continue
        device.last_ip = device.config.last_ip
        device.save()


def migrate_last_ip_backward(apps, schema_editor):
    device_model = apps.get_model('config', 'Device')
    devices = device_model.objects.all().select_related('config')
    for device in devices:
        if not hasattr(device, 'config'):
            continue
        device.config.last_ip = device.last_ip
        device.config.save()


def migrate_status_forward(apps, schema_editor):
    config_model = apps.get_model('config', 'Config')
    for config in config_model.objects.all():
        if config.status != 'running':
            continue
        config.status = 'applied'
        config.save()


def migrate_status_backward(apps, schema_editor):
    config_model = apps.get_model('config', 'Config')
    for config in config_model.objects.all():
        if config.status != 'applied':
            continue
        config.status = 'running'
        config.save()


class Migration(migrations.Migration):

    dependencies = [('config', '0012_auto_20180219_1501')]

    operations = [
        migrations.AddField(
            model_name='device',
            name='last_ip',
            field=models.GenericIPAddressField(
                blank=True,
                help_text=(
                    'indicates the IP address logged from the last '
                    'request coming from the device'
                ),
                null=True,
            ),
        ),
        migrations.RunPython(migrate_last_ip_forward, migrate_last_ip_backward),
        migrations.RemoveField(model_name='config', name='last_ip'),
        migrations.AddField(
            model_name='device',
            name='management_ip',
            field=models.GenericIPAddressField(
                blank=True,
                help_text='ip address of the management interface, if available',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='config',
            name='status',
            field=model_utils.fields.StatusField(
                choices=[
                    ('modified', 'modified'),
                    ('applied', 'applied'),
                    ('error', 'error'),
                ],
                default='modified',
                help_text=(
                    '"modified" means the configuration is not applied yet; '
                    '\n"applied" means the configuration is applied successfully; '
                    '\n"error" means the configuration caused issues and it '
                    'was rolled back;'
                ),
                max_length=100,
                no_check_for_status=True,
                verbose_name='configuration status',
            ),
        ),
        migrations.RunPython(migrate_status_forward, migrate_status_backward),
        migrations.AlterField(
            model_name='device',
            name='notes',
            field=models.TextField(blank=True, help_text='internal notes'),
        ),
    ]
