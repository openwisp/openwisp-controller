# Generated migration to replace third-party jsonfield with Django built-in JSONField

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('config', '0060_cleanup_api_task_notification_types'),
    ]

    operations = [
        # Replace jsonfield.fields.JSONField with django.db.models.JSONField
        migrations.AlterField(
            model_name='config',
            name='context',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    'Additional <a href="http://netjsonconfig.openwisp.org/'
                    'en/stable/general/basics.html#context" target="_blank">'
                    "context (configuration variables)</a> in JSON format"
                ),
            ),
        ),
        migrations.AlterField(
            model_name='template',
            name='config',
            field=models.JSONField(
                verbose_name='configuration',
                default=dict,
                help_text='configuration in NetJSON DeviceConfiguration format',
            ),
        ),
        migrations.AlterField(
            model_name='template',
            name='default_values',
            field=models.JSONField(
                verbose_name='Default Values',
                default=dict,
                blank=True,
                help_text=(
                    "A dictionary containing the default "
                    "values for the variables used by this "
                    "template; these default variables will "
                    "be used during schema validation."
                ),
            ),
        ),
        migrations.AlterField(
            model_name='devicegroup',
            name='meta_data',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Group meta data, use this field to store data which is related"
                    " to this group and can be retrieved via the REST API."
                ),
                verbose_name='Metadata',
            ),
        ),
        migrations.AlterField(
            model_name='devicegroup',
            name='context',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "This field can be used to add meta data for the group"
                    ' or to add "Configuration Variables" to the devices.'
                ),
                verbose_name='Configuration Variables',
            ),
        ),
        migrations.AlterField(
            model_name='organizationconfigsettings',
            name='context',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    'This field can be used to add "Configuration Variables"'
                    " to the devices."
                ),
                verbose_name='Configuration Variables',
            ),
        ),
    ]
