import django.db.models.deletion
from django.db import migrations, models
from swapper import get_model_name


class Migration(migrations.Migration):

    dependencies = [('connection', '0006_name_unique_per_organization')]

    operations = [
        migrations.AlterField(
            model_name='credentials',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=get_model_name('openwisp_users', 'Organization'),
                verbose_name='organization',
            ),
        )
    ]
