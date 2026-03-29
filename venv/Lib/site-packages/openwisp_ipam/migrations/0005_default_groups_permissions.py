from django.conf import settings
from django.db import migrations
from openwisp_users.migrations import (
    create_default_groups as base_create_default_groups,
)

from openwisp_ipam.migrations import assign_permissions_to_groups


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("openwisp_ipam", "0004_subnet_organization_unique_together"),
    ]

    operations = [
        migrations.RunPython(
            base_create_default_groups, reverse_code=migrations.RunPython.noop
        ),
        migrations.RunPython(
            assign_permissions_to_groups, reverse_code=migrations.RunPython.noop
        ),
    ]
