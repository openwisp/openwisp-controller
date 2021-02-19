import django.db.models.deletion
from django.db import migrations, models
from swapper import get_model_name


class Migration(migrations.Migration):

    dependencies = [('config', '0034_template_required')]

    operations = [
        migrations.AlterField(
            model_name='organizationconfigsettings',
            name='organization',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='config_settings',
                to=get_model_name('openwisp_users', 'Organization'),
                verbose_name='organization',
            ),
        ),
        migrations.AlterField(
            model_name='template',
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
            model_name='vpn',
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
            model_name='device',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=get_model_name('openwisp_users', 'Organization'),
                verbose_name='organization',
            ),
        ),
    ]
