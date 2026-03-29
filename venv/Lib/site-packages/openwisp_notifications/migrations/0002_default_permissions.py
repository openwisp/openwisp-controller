from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Permission
from django.db import migrations

from openwisp_notifications.migrations import get_swapped_model
from openwisp_users.migrations import (
    create_default_groups as base_create_default_groups,
)


def add_default_permissions(apps, schema_editor):
    group = get_swapped_model(apps, "openwisp_users", "Group")

    # To populate all the permissions
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    operator = group.objects.filter(name="Operator")
    operator = operator.first()

    admin = group.objects.filter(name="Administrator")
    admin = admin.first()

    permissions = [
        Permission.objects.get(
            content_type__app_label="openwisp_notifications",
            codename="add_notification",
        ).pk,
        Permission.objects.get(
            content_type__app_label="openwisp_notifications",
            codename="change_notification",
        ).pk,
        Permission.objects.get(
            content_type__app_label="openwisp_notifications",
            codename="delete_notification",
        ).pk,
    ]
    permissions += operator.permissions.all()
    operator.permissions.set(permissions)

    permissions += admin.permissions.all()
    admin.permissions.set(permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("openwisp_notifications", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            base_create_default_groups, reverse_code=migrations.RunPython.noop
        ),
        migrations.RunPython(
            add_default_permissions, reverse_code=migrations.RunPython.noop
        ),
    ]
