# Generated by Django 3.0.6 on 2020-05-10 07:25

import re

import django.core.validators
from django.db import migrations, models

from .. import settings as app_settings


class Migration(migrations.Migration):
    dependencies = [('config', '0028_template_default_values')]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='name',
            field=models.CharField(
                db_index=True,
                max_length=64,
                validators=[
                    django.core.validators.RegexValidator(
                        re.compile(
                            '^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\\-]{0,61}[a-zA-Z0-9])'
                            '(\\.([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\\-]{0,61}'
                            '[a-zA-Z0-9]))*$|^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
                        ),
                        code='invalid',
                        message='Must be either a valid hostname or mac address.',
                    )
                ],
                help_text=('must be either a valid hostname or mac address'),
            ),
        ),
        migrations.AlterField(
            model_name='vpn',
            name='backend',
            field=models.CharField(
                choices=app_settings.VPN_BACKENDS,
                help_text='Select VPN configuration backend',
                max_length=128,
                verbose_name='VPN backend',
            ),
        ),
    ]
