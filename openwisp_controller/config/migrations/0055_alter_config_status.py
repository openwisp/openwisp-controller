# Generated by Django 4.2.10 on 2024-03-01 16:35

import model_utils.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("config", "0054_device__is_deactivated"),
    ]

    operations = [
        migrations.AlterField(
            model_name="config",
            name="status",
            field=model_utils.fields.StatusField(
                choices=[
                    ("modified", "modified"),
                    ("applied", "applied"),
                    ("error", "error"),
                    ("deactivating", "deactivating"),
                    ("deactivated", "deactivated"),
                ],
                default="modified",
                help_text=(
                    '"modified" means the configuration is not applied yet;'
                    ' \n"applied" means the configuration is applied successfully;'
                    ' \n"error" means the configuration caused issues and it was'
                    ' rolled back;'
                    '"deactivating" means the device has been deactivated and all the'
                    ' configuration is being removed; \n'
                    '"deactivated" means the configuration has been removed from'
                    ' the device;'
                ),
                max_length=100,
                no_check_for_status=True,
                verbose_name="configuration status",
            ),
        ),
    ]
