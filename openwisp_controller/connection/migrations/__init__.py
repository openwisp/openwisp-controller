from django.contrib.auth.models import Permission

from ...migrations import create_default_permissions


def assign_permissions_to_groups(apps, schema_editor):
    create_default_permissions(apps, schema_editor)
    operators_and_admins_can_change = ['deviceconnection']
    only_admins_can_manage = ['credentials']
    manage_operations = ['add', 'change', 'delete']
    Group = apps.get_model('openwisp_users', 'Group')

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

    for model_name in only_admins_can_manage:
        for operation in manage_operations:
            admin.permissions.add(
                Permission.objects.get(
                    codename='{}_{}'.format(operation, model_name)
                ).pk
            )
