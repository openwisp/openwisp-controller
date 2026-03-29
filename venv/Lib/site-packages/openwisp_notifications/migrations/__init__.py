import swapper
from django.contrib.auth.management import create_permissions


def get_swapped_model(apps, app_name, model_name):
    model_path = swapper.get_model_name(app_name, model_name)
    app, model = swapper.split(model_path)
    return apps.get_model(app, model)


def assign_organizationnotificationsettings_permissions_to_groups(apps, schema_editor):
    # Populate permissions
    OrganizationNotificationSetting = get_swapped_model(
        apps, "openwisp_notifications", "OrganizationNotificationSettings"
    )
    app_config = apps.get_app_config(OrganizationNotificationSetting._meta.app_label)
    app_config.models_module = True
    create_permissions(app_config, apps=apps, verbosity=0)

    operator_and_admin_operations = ["view"]
    admin_operations = ["change"]
    Group = get_swapped_model(apps, "openwisp_users", "Group")
    Permission = apps.get_model("auth", "Permission")

    try:
        admin = Group.objects.get(name="Administrator")
        operator = Group.objects.get(name="Operator")
    # consider failures custom cases
    # that do not have to be dealt with
    except Group.DoesNotExist:
        return

    for operation in operator_and_admin_operations:
        permission = Permission.objects.get(
            codename="{}_{}".format(operation, "organizationnotificationsettings"),
        )
        admin.permissions.add(permission.pk)
        operator.permissions.add(permission.pk)

    for operation in admin_operations:
        permission = Permission.objects.get(
            codename="{}_{}".format(operation, "organizationnotificationsettings"),
        )
        admin.permissions.add(permission.pk)


def create_organization_notification_settings(apps, schema_editor):
    OrganizationNotificationSettings = get_swapped_model(
        apps, "openwisp_notifications", "OrganizationNotificationSettings"
    )
    Organization = get_swapped_model(apps, "openwisp_users", "Organization")

    for org in Organization.objects.iterator():
        org_setting = OrganizationNotificationSettings(organization=org)
        org_setting.full_clean()
        org_setting.save()


def reverse_create_organization_notification_settings(apps, schema_editor):
    OrganizationNotificationSettings = get_swapped_model(
        apps, "openwisp_notifications", "OrganizationNotificationSettings"
    )
    OrganizationNotificationSettings.objects.all().delete()
