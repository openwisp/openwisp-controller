import openwisp_controller.pki.base.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pki", "0012_alter_ca_extensions_alter_ca_key_length_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ca",
            name="validity_start",
            field=models.DateTimeField(
                blank=True,
                default=openwisp_controller.pki.base.models.default_validity_start,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="cert",
            name="validity_start",
            field=models.DateTimeField(
                blank=True,
                default=openwisp_controller.pki.base.models.default_validity_start,
                null=True,
            ),
        ),
    ]
