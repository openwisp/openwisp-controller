from django.contrib.auth.models import Permission

from ...migrations import create_default_permissions, get_swapped_model


def _assign_permissions_to_groups(apps, schema_editor, operators_and_admins_can_change):
    create_default_permissions(apps, schema_editor)
    manage_operations = ["add", "change", "delete"]
    Group = get_swapped_model(apps, "openwisp_users", "Group")

    try:
        admin = Group.objects.get(name="Administrator")
        operator = Group.objects.get(name="Operator")
    # consider failures custom cases
    # that do not have to be dealt with
    except Group.DoesNotExist:
        return

    for model_name in operators_and_admins_can_change:
        for operation in manage_operations:
            permission = Permission.objects.get(
                codename="{}_{}".format(operation, model_name)
            )
            admin.permissions.add(permission.pk)
            operator.permissions.add(permission.pk)


def assign_permissions_to_groups(apps, schema_editor):
    _assign_permissions_to_groups(
        apps,
        schema_editor,
        operators_and_admins_can_change=["location", "floorplan", "devicelocation"],
    )


def assign_geo_settings_permissions_to_groups(apps, schema_editor):
    _assign_permissions_to_groups(
        apps, schema_editor, operators_and_admins_can_change=["organizationgeosettings"]
    )
