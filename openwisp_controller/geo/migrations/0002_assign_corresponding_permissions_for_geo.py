from django.db import migrations
from django.contrib.auth.models import Permission


def assign_permissions_to_groups(apps, schema_editor):
    Group = apps.get_model('openwisp_users', 'Group')
    admin = Group.objects.get(name='Administrator')
    operator = Group.objects.get(name='Operator')
    operators_and_admins_can_change = ['location', 'floorplan', ]
    manage_operations = ['add', 'change', 'delete']

    for model_name in operators_and_admins_can_change:
        for operation in manage_operations:
            permission = Permission.objects.get(
                codename='{}_{}'.format(operation, model_name)
            )
            admin.permissions.add(permission.pk)
            operator.permissions.add(permission.pk)


class Migration(migrations.Migration):
    dependencies = [
        ('openwisp_users', '0004_default_groups'),
        ('geo', '0001_initial')
    ]

    operations = [
        migrations.RunPython(
            assign_permissions_to_groups,
            reverse_code=migrations.RunPython.noop
        )
    ]
