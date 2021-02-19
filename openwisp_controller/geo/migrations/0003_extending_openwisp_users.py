import django.db.models.deletion
from django.db import migrations, models
from swapper import get_model_name


class Migration(migrations.Migration):

    dependencies = [('geo', '0002_default_groups_permissions')]

    operations = [
        migrations.AlterField(
            model_name='location',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=get_model_name('openwisp_users', 'Organization'),
                verbose_name='organization',
            ),
        ),
        migrations.AlterField(
            model_name='floorplan',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=get_model_name('openwisp_users', 'Organization'),
                verbose_name='organization',
            ),
        ),
    ]
