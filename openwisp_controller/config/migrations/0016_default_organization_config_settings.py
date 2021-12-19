from django.db import migrations

from ...migrations import get_swapped_model


def create_default_config_settings_organization(apps, schema_editor):
    organization_model = get_swapped_model(apps, 'openwisp_users', 'Organization')
    config_settings_model = apps.get_model('config', 'OrganizationConfigSettings')
    for organization in organization_model.objects.all():
        try:
            organization.config_settings
        except organization_model.config_settings.RelatedObjectDoesNotExist:
            # if there is no OrganizationConfigSettings
            # associated to this organization, create it
            config_settings_model.objects.create(organization=organization)


class Migration(migrations.Migration):
    dependencies = [
        ('config', '0015_default_groups_permissions'),
    ]
    operations = [
        migrations.RunPython(
            create_default_config_settings_organization,
            reverse_code=migrations.RunPython.noop,
        )
    ]
