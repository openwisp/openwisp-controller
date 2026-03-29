import swapper
from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Permission


def get_swapped_model(apps, app_name, model_name):
    model_path = swapper.get_model_name(app_name, model_name)
    app, model = swapper.split(model_path)
    return apps.get_model(app, model)


def create_default_permissions(apps, schema_editor):
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None


def assign_permissions_to_groups(apps, schema_editor):
    create_default_permissions(apps, schema_editor)
    admins_can_manage = ["subnet", "ipaddress"]
    operators_can_manage = ["ipaddress"]
    manage_operations = ["add", "change", "delete", "view"]
    Group = get_swapped_model(apps, "openwisp_users", "Group")

    admin = Group.objects.get(name="Administrator")
    operator = Group.objects.get(name="Operator")

    # Administrator - Can managae both ipaddress and subnet
    for model_name in admins_can_manage:
        for operation in manage_operations:
            permission = Permission.objects.get(
                codename="{}_{}".format(operation, model_name)
            )
            admin.permissions.add(permission.pk)

    # Operator - Can manage ipaddress but can only `view` subnet
    for model_name in operators_can_manage:
        for operation in manage_operations:
            operator.permissions.add(
                Permission.objects.get(
                    codename="{}_{}".format(operation, model_name)
                ).pk
            )

    try:
        permission = Permission.objects.get(codename="view_subnet")
        operator.permissions.add(permission.pk)
    except Permission.DoesNotExist:
        pass
