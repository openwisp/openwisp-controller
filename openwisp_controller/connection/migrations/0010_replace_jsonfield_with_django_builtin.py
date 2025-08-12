# Generated migration to replace third-party jsonfield with Django built-in JSONField

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('connection', '0009_alter_deviceconnection_unique_together'),
    ]

    operations = [
        # Replace jsonfield.fields.JSONField with django.db.models.JSONField
        migrations.AlterField(
            model_name='credentials',
            name='params',
            field=models.JSONField(
                verbose_name='parameters',
                default=dict,
                help_text='global connection parameters',
            ),
        ),
        migrations.AlterField(
            model_name='deviceconnection',
            name='params',
            field=models.JSONField(
                verbose_name='parameters',
                default=dict,
                blank=True,
                help_text=(
                    "local connection parameters (will override "
                    "the global parameters if specified)"
                ),
            ),
        ),
        migrations.AlterField(
            model_name='command',
            name='input',
            field=models.JSONField(
                blank=True,
                null=True,
            ),
        ),
    ]
