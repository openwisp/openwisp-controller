from django.db import migrations


def change_owzt_to_global(apps, schema_editor):
    Template = apps.get_model('config', 'Template')
    updated_templates = set()
    for template in Template.objects.filter(
        type='vpn', vpn__backend='openwisp_controller.vpn_backends.ZeroTier'
    ).iterator():
        if 'zerotier' in template.config:
            for item in template.config.get('zerotier', []):
                if item.get('name') == 'ow_zt':
                    item['name'] = 'global'
                    updated_templates.add(template)
    Template.objects.bulk_update(updated_templates, ['config'])


class Migration(migrations.Migration):
    dependencies = [('config', '0058_alter_vpnclient_template')]

    operations = [
        migrations.RunPython(
            change_owzt_to_global, reverse_code=migrations.RunPython.noop
        )
    ]
