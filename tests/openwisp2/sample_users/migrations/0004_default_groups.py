# Manually Created

import swapper
from django.db import migrations

from openwisp_users.migrations import (
    allow_admins_change_organization,
    allow_operator_view_organization,
    create_default_groups,
    set_default_organization_uuid,
    update_admins_permissions,
)


class Migration(migrations.Migration):
    org_model = swapper.get_model_name('openwisp_users', 'organization')
    model_app_label = swapper.split(org_model)[0]
    dependencies = [(model_app_label, '0001_initial')]

    operations = [
        migrations.RunPython(
            set_default_organization_uuid, reverse_code=migrations.RunPython.noop
        ),
        migrations.RunPython(
            create_default_groups, reverse_code=migrations.RunPython.noop
        ),
        migrations.RunPython(
            update_admins_permissions, reverse_code=migrations.RunPython.noop
        ),
        migrations.RunPython(
            allow_admins_change_organization, reverse_code=migrations.RunPython.noop
        ),
        migrations.RunPython(
            allow_operator_view_organization, reverse_code=migrations.RunPython.noop
        ),
    ]
