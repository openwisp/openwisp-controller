# Generated by Django 3.2.19 on 2023-06-26 12:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('config', '0047_add_organizationlimits'),
    ]

    operations = [
        migrations.AddField(
            model_name='vpn',
            name='network_id',
            field=models.CharField(blank=True, max_length=16),
        ),
    ]
