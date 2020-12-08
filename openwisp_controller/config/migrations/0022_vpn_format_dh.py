from django.db import migrations


def format_dh(apps, schema_editor):
    Vpn = apps.get_model('config', 'Vpn')

    for vpn in Vpn.objects.all():
        if vpn.dh.startswith("b'") and vpn.dh.endswith("'"):
            vpn.dh = vpn.dh[2:-1]
            vpn.save()


class Migration(migrations.Migration):

    dependencies = [('config', '0021_vpn_key')]

    operations = [
        migrations.RunPython(format_dh, reverse_code=migrations.RunPython.noop)
    ]
