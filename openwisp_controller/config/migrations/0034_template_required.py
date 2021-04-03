# Generated by Django 3.1.1 on 2020-12-02 23:56

from django.conf import settings
from django.db import migrations, models

import openwisp_controller.config.sortedm2m.fields


class Migration(migrations.Migration):

    dependencies = [('config', '0033_name_unique_per_organization')]

    operations = [
        migrations.AddField(
            model_name='template',
            name='required',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    'if checked, will force the assignment of this template to all the '
                    'devices of the organization (if no organization is selected, it '
                    'will be required for every device in the system)'
                ),
                verbose_name='required',
            ),
        ),
        migrations.AlterField(
            model_name='config',
            name='templates',
            field=openwisp_controller.config.sortedm2m.fields.SortedManyToManyField(
                blank=True,
                help_text='configuration templates, applied from first to last',
                related_name='config_relations',
                to=settings.CONFIG_TEMPLATE_MODEL,
                verbose_name='templates',
            ),
        ),
    ]
