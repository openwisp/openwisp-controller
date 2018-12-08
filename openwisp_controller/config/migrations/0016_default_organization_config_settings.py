from django.db import migrations


def make_default_config_settings_organization(apps, schema_editor):
    organization_model = apps.get_model('openwisp_users', 'Organization')
    config_settings_model = apps.get_model(
        'config',
        'OrganizationConfigSettings'
    )
    for organization in organization_model.objects.all():
        try:
            config_setting = organization.config_settings
        except organization_model.config_settings.RelatedObjectDoesNotExist:
            # If there is no OrganizationConfigSettings associated with said organization
            config_setting = config_settings_model.objects.create(organization=organization)
            # creates OrganizationConfigSettings object corresponding to the organization


class Migration(migrations.Migration):
    dependencies = [
       ('openwisp_users', '0003_default_organization'),
       ('config', '0015_default_groups_permissions'),
    ]

    operations = [
        migrations.RunPython(
            make_default_config_settings_organization,
            reverse_code=migrations.RunPython.noop
        )
    ]
