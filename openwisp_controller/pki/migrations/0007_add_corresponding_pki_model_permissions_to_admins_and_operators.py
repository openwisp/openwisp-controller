from django.db import migrations
from django.contrib.auth.models import Permission


def assign_permissions_to_groups(apps, schema_editor):
    Group = apps.get_model('openwisp_users', 'Group')
    admin = Group.objects.get(name='Administrator')
    operator = Group.objects.get(name='Operator')
    operators_read_only_admins_manage = ['ca', 'cert']
    manage_operations = ['add', 'change', 'delete']

    for model_name in operators_read_only_admins_manage:
        try:
            permission = Permission.objects.get(codename="view_{}".format(model_name))
            operator.permissions.add(permission.pk)
        except Permission.DoesNotExist:
            pass

        for operation in manage_operations:
            admin.permissions.add(
                Permission.objects.get(codename="{}_{}".format(operation, model_name)).pk
            )


class Migration(migrations.Migration):
    dependencies = [
        ('openwisp_users', '0004_default_groups'),
        ('pki', '0006_add_x509_passphrase_field'),
    ]
    operations = [
            migrations.RunPython(
                assign_permissions_to_groups,
                reverse_code=migrations.RunPython.noop
            )
    ]
