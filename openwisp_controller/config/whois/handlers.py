from django.db.models.signals import post_delete, post_save
from swapper import load_model

from .. import settings as app_settings
from ..signals import device_activated, device_deactivated


def reconcile_device_whois_references(sender, instance, **kwargs):
    WHOISInfo = load_model("config", "WHOISInfo")
    WHOISInfo.update_reference_state([instance.last_ip])


def _whois_receivers():
    Device = load_model("config", "Device")
    WHOISInfo = load_model("config", "WHOISInfo")
    OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")

    return (
        (
            post_delete,
            WHOISInfo.device_whois_info_delete_handler,
            Device,
            "device.delete_whois_info",
        ),
        (
            device_activated,
            reconcile_device_whois_references,
            Device,
            "device.activate_whois_info",
        ),
        (
            device_deactivated,
            reconcile_device_whois_references,
            Device,
            "device.deactivate_whois_info",
        ),
        (
            post_save,
            WHOISInfo.invalidate_org_settings_cache,
            OrganizationConfigSettings,
            "invalidate_org_config_cache_on_org_config_save",
        ),
        (
            post_delete,
            WHOISInfo.invalidate_org_settings_cache,
            OrganizationConfigSettings,
            "invalidate_org_config_cache_on_org_config_delete",
        ),
    )


def connect_whois_handlers():
    if app_settings.WHOIS_CONFIGURED:
        for signal, receiver, sender, uid in _whois_receivers():
            signal.connect(receiver, sender=sender, dispatch_uid=uid)
