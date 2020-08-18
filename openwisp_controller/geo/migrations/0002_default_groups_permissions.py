from django.db import migrations

from . import assign_permissions_to_groups


class Migration(migrations.Migration):
    dependencies = [('openwisp_users', '0004_default_groups'), ('geo', '0001_initial')]
    operations = [
        migrations.RunPython(
            assign_permissions_to_groups, reverse_code=migrations.RunPython.noop
        )
    ]
