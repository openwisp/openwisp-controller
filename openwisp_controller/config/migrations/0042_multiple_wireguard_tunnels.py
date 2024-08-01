# Generated by Django 4.0.5 on 2022-06-24 06:31

from django.db import migrations

from ..migrations import get_swapped_model


def get_wireguard_and_vxlan_wireguard_templates(apps):
    template_model = get_swapped_model(apps, 'config', 'Template')
    return template_model.objects.filter(type='vpn', vpn__backend__contains='Wireguard')


def allow_multiple_wireguard_tunneling(apps, schema_editor):
    templates = get_wireguard_and_vxlan_wireguard_templates(apps).iterator()
    for template in templates:
        config = template.config
        interfaces = config['interfaces']
        vpn_id = template.vpn.pk.hex
        changed = False
        for interface in interfaces:
            interface_type = interface.get('type', None)
            private_key = interface.get('private_key', None)
            if interface_type != 'wireguard' or not private_key:
                continue
            if private_key not in [
                '{{private_key}}',
                '{{ private_key }}',
            ]:
                continue
            interface['private_key'] = '{{pvt_key_%s}}' % vpn_id
            changed = True
        if not changed:
            continue
        template.config = config
        template.save(update_fields=['config'])


def disallow_multiple_wireguard_tunneling(apps, schema_editor):
    templates = get_wireguard_and_vxlan_wireguard_templates(apps).iterator()
    for template in templates:
        config = template.config
        interfaces = config['interfaces']
        vpn_id = template.vpn.pk.hex
        changed = False
        for interface in interfaces:
            interface_type = interface.get('type', None)
            private_key = interface.get('private_key', None)
            if interface_type != 'wireguard' or not private_key:
                continue
            if f'pvt_key_{vpn_id}' not in private_key:
                continue
            interface['private_key'] = '{{private_key}}'
            changed = True
        if not changed:
            continue
        template.config = config
        template.save(update_fields=['config'])


class Migration(migrations.Migration):
    dependencies = [
        ('config', '0041_default_groups_organizationconfigsettings_permission'),
    ]

    operations = [
        migrations.RunPython(
            code=allow_multiple_wireguard_tunneling,
            reverse_code=disallow_multiple_wireguard_tunneling,
        ),
    ]
