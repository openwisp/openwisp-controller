from django.db import migrations

from openwisp_controller.subnet_division.migrations import assign_permissions_to_groups


class Migration(migrations.Migration):
    dependencies = [('sample_subnet_division', '0001_initial')]

    operations = [
        migrations.RunPython(
            assign_permissions_to_groups, reverse_code=migrations.RunPython.noop
        )
    ]
