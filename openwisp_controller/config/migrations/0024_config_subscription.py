# Generated by Django 2.0.13 on 2019-07-18 18:09

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('config', '0023_templatesubscription'),
    ]

    operations = [
        migrations.AddField(
            model_name='config',
            name='subscription',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='config.TemplateSubscription'),
        ),
    ]