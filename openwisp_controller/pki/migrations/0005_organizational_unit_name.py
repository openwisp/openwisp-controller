# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-02-19 11:53
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pki', '0004_auto_20180106_1814')]

    operations = [
        migrations.AddField(
            model_name='ca',
            name='organizational_unit_name',
            field=models.CharField(
                blank=True, max_length=64, verbose_name='organizational unit name'
            ),
        ),
        migrations.AddField(
            model_name='cert',
            name='organizational_unit_name',
            field=models.CharField(
                blank=True, max_length=64, verbose_name='organizational unit name'
            ),
        ),
    ]
