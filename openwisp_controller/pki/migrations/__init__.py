from django.contrib.auth.models import Permission

from ...migrations import create_default_permissions


def assign_permissions_to_groups(apps, schema_editor):
    create_default_permissions(apps, schema_editor)
    operators_read_only_admins_manage = ['ca', 'cert']
    manage_operations = ['add', 'change', 'delete']
    Group = apps.get_model('openwisp_users', 'Group')

    try:
        admin = Group.objects.get(name='Administrator')
        operator = Group.objects.get(name='Operator')
    # consider failures custom cases
    # that do not have to be dealt with
    except Group.DoesNotExist:
        return

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
