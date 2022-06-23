import subprocess

from django.contrib.auth.models import Permission

from ...migrations import create_default_permissions, get_swapped_model


def update_vpn_dhparam_length(apps, schema_editor):
    vpn_model = get_swapped_model(apps, 'config', 'Vpn')
    for vpn in vpn_model.objects.all().iterator():
        if len(vpn.dh) < 424:
            print(
                (
                    '\n  Generating a new 2048 bit DH key for '
                    f'{vpn.name}, this may take a while...'
                ),
                end='',
            )
            vpn.dh = subprocess.check_output(
                'openssl dhparam 2048 2> /dev/null', shell=True
            ).decode('utf-8')
            vpn.save()


def assign_permissions_to_groups(apps, schema_editor):
    create_default_permissions(apps, schema_editor)
    operators_and_admins_can_change = ['device', 'config', 'template']
    operators_read_only_admins_manage = ['vpn']
    manage_operations = ['add', 'change', 'delete']
    Group = get_swapped_model(apps, 'openwisp_users', 'Group')

    try:
        admin = Group.objects.get(name='Administrator')
        operator = Group.objects.get(name='Operator')
    # consider failures custom cases
    # that do not have to be dealt with
    except Group.DoesNotExist:
        return

    for model_name in operators_and_admins_can_change:
        for operation in manage_operations:
            permission = Permission.objects.get(
                codename='{}_{}'.format(operation, model_name)
            )
            admin.permissions.add(permission.pk)
            operator.permissions.add(permission.pk)

    for model_name in operators_read_only_admins_manage:
        try:
            permission = Permission.objects.get(codename='view_{}'.format(model_name))
            operator.permissions.add(permission.pk)
        except Permission.DoesNotExist:
            pass
        for operation in manage_operations:
            admin.permissions.add(
                Permission.objects.get(
                    codename='{}_{}'.format(operation, model_name)
                ).pk
            )


def assign_devicegroup_permissions_to_groups(apps, schema_editor):
    create_default_permissions(apps, schema_editor)
    operator_and_admin_operations = ['add', 'change', 'delete', 'view']
    Group = get_swapped_model(apps, 'openwisp_users', 'Group')

    try:
        admin = Group.objects.get(name='Administrator')
        operator = Group.objects.get(name='Operator')
    # consider failures custom cases
    # that do not have to be dealt with
    except Group.DoesNotExist:
        return

    for operation in operator_and_admin_operations:
        permission = Permission.objects.get(
            codename='{}_{}'.format(operation, 'devicegroup')
        )
        admin.permissions.add(permission.pk)
        operator.permissions.add(permission.pk)


def assign_organization_config_settings_permissions_to_groups(apps, schema_editor):
    create_default_permissions(apps, schema_editor)
    operator_operations = ['view']
    admin_operations = operator_operations + ['change']
    Group = get_swapped_model(apps, 'openwisp_users', 'Group')
    try:
        admin = Group.objects.get(name='Administrator')
        operator = Group.objects.get(name='Operator')
    # consider failures custom cases
    # that do not have to be dealt with
    except Group.DoesNotExist:
        return
    for operation in admin_operations:
        permission = Permission.objects.get(
            codename='{}_{}'.format(operation, 'organizationconfigsettings')
        )
        if operation in operator_operations:
            operator.permissions.add(permission.pk)
        admin.permissions.add(permission.pk)
