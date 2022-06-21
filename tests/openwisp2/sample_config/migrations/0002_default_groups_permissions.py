from django.db import migrations

from openwisp_controller.config.migrations import (
    assign_devicegroup_permissions_to_groups,
    assign_organization_config_settings_permissions_to_groups,
    assign_permissions_to_groups,
)


class Migration(migrations.Migration):
    dependencies = [('sample_config', '0001_initial')]

    operations = [
        migrations.RunPython(
            assign_permissions_to_groups, reverse_code=migrations.RunPython.noop
        ),
        migrations.RunPython(
            assign_devicegroup_permissions_to_groups,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            code=assign_organization_config_settings_permissions_to_groups,
            reverse_code=migrations.operations.special.RunPython.noop,
        ),
    ]
