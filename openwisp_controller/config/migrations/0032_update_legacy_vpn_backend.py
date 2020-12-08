from django.db import migrations


def update_legacy_vpn_backend(apps, schema_editor):
    Vpn = apps.get_model('config', 'Vpn')
    Vpn.objects.filter(backend='django_netjsonconfig.vpn_backends.OpenVpn').update(
        backend='openwisp_controller.vpn_backends.OpenVpn'
    )


class Migration(migrations.Migration):

    dependencies = [('config', '0031_update_vpn_dh_param')]

    operations = [
        migrations.RunPython(
            update_legacy_vpn_backend, reverse_code=migrations.RunPython.noop
        )
    ]
