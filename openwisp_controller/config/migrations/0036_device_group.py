# Generated by Django 3.1.12 on 2021-06-14 17:51

import collections
import uuid

import django.db.models.deletion
import django.utils.timezone
import jsonfield.fields
import model_utils.fields
import swapper
from django.db import migrations, models

import openwisp_users.mixins

from . import assign_devicegroup_permissions_to_groups


class Migration(migrations.Migration):
    dependencies = [
        ('config', '0035_device_name_unique_optional'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceGroup',
            fields=[
                (
                    'id',
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    'created',
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name='created',
                    ),
                ),
                (
                    'modified',
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name='modified',
                    ),
                ),
                ('name', models.CharField(max_length=60)),
                (
                    'description',
                    models.TextField(blank=True, help_text='internal notes'),
                ),
                (
                    'meta_data',
                    jsonfield.fields.JSONField(
                        blank=True,
                        default=dict,
                        dump_kwargs={'ensure_ascii': False, 'indent': 4},
                        load_kwargs={'object_pairs_hook': collections.OrderedDict},
                        help_text=(
                            'Group meta data, use this field to store data which is'
                            ' related to this group and can be retrieved via the'
                            ' REST API.'
                        ),
                        verbose_name='Metadata',
                    ),
                ),
                (
                    'organization',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=swapper.get_model_name('openwisp_users', 'Organization'),
                        verbose_name='organization',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Device Group',
                'verbose_name_plural': 'Device Groups',
                'abstract': False,
                'swappable': 'CONFIG_DEVICEGROUP_MODEL',
            },
            bases=(openwisp_users.mixins.ValidateOrgMixin, models.Model),
        ),
        migrations.AlterUniqueTogether(
            name='devicegroup',
            unique_together={('organization', 'name')},
        ),
        migrations.AddField(
            model_name='device',
            name='group',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=swapper.get_model_name('config', 'DeviceGroup'),
                verbose_name='group',
            ),
        ),
        migrations.RunPython(
            code=assign_devicegroup_permissions_to_groups,
            reverse_code=migrations.operations.special.RunPython.noop,
        ),
    ]
