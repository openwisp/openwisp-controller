import django.db.models.deletion
from django.db import migrations, models
from swapper import get_model_name


class Migration(migrations.Migration):

    dependencies = [('pki', '0009_common_name_maxlength_64')]

    operations = [
        migrations.AlterField(
            model_name='ca',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=get_model_name('openwisp_users', 'Organization'),
                verbose_name='organization',
            ),
        ),
        migrations.AlterField(
            model_name='cert',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=get_model_name('openwisp_users', 'Organization'),
                verbose_name='organization',
            ),
        ),
    ]
