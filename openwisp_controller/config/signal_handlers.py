from django.db.models.signals import pre_save
from django.dispatch import receiver

from openwisp_controller.config.models import Config, Device, OrganizationConfigSettings
from openwisp_controller.config.signals import config_modified


@receiver(pre_save, sender=OrganizationConfigSettings)
def update_configs_on_org_settings_change(sender, instance, **kwargs):
    try:
        old_instance = OrganizationConfigSettings.objects.get(pk=instance.pk)
        old_vars = old_instance.context or {}
    except OrganizationConfigSettings.DoesNotExist:
        old_vars = {}

    new_vars = instance.context or {}

    if old_vars != new_vars:
        devices = Device.objects.filter(organization=instance.organization)
        for device in devices:
            try:
                config = device.config
                if config.status == "applied":
                    config.status = "modified"
                    config.save()
                    config_modified.send(
                        sender=Config,
                        instance=config,
                        device=device,
                        config=config,
                        previous_status="applied",
                        action="updated_via_org_settings",
                    )
            except Config.DoesNotExist:
                pass
