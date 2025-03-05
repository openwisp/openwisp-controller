from django.db import migrations
import json

def change_owzt_to_global(apps, schema_editor):
    Template = apps.get_model('config', 'Template')
    for template in Template.objects.filter(type='vpn',vpn__backend='openwisp_controller.vpn_backends.ZeroTier'):
        config = json.loads(template.config)
        if 'zerotier' in config:
            for item in config.get('zerotier',[]):
                if item.get('name') == 'ow_zt':
                    item['name'] = 'global'

class Migration(migrations.Migration):
    dependencies = [('config', '0055_alter_config_status')]

    operations = [
        migrations.RunPython(change_owzt_to_global, reverse_code=migrations.RunPython.noop)
    ]
    