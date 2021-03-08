from django.contrib.auth.models import Permission

from ...migrations import create_default_permissions, get_swapped_model


def assign_permissions_to_groups(apps, schema_editor):
    create_default_permissions(apps, schema_editor)
    operators_and_admins_can_manage = ['subnetdivisionrule']
    admin_manage_operations = ['add', 'change', 'delete', 'view']
    operator_manage_operations = ['view']
    Group = get_swapped_model(apps, 'openwisp_users', 'Group')

    try:
        admin = Group.objects.get(name='Administrator')
        operator = Group.objects.get(name='Operator')
    # consider failures custom cases
    # that do not have to be dealt with
    except Group.DoesNotExist:
        return

    for model_name in operators_and_admins_can_manage:
        for operation in admin_manage_operations:
            permission = Permission.objects.get(
                codename='{}_{}'.format(operation, model_name)
            )
            admin.permissions.add(permission.pk)

    for model_name in operators_and_admins_can_manage:
        for operation in operator_manage_operations:
            permission = Permission.objects.get(
                codename='{}_{}'.format(operation, model_name)
            )
            operator.permissions.add(permission.pk)
