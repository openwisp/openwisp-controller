from django.db.models.signals import post_delete, post_save
from swapper import load_model

from .. import settings as app_settings


def connect_whois_handlers():
    if not app_settings.WHOIS_CONFIGURED:
        return

    Device = load_model("config", "Device")
    WHOISInfo = load_model("config", "WHOISInfo")
    OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")

    post_delete.connect(
        WHOISInfo.device_whois_info_delete_handler,
        sender=Device,
        dispatch_uid="device.delete_whois_info",
    )
    post_save.connect(
        WHOISInfo.invalidate_org_settings_cache,
        sender=OrganizationConfigSettings,
        dispatch_uid="invalidate_org_config_cache_on_org_config_save",
    )
    post_delete.connect(
        WHOISInfo.invalidate_org_settings_cache,
        sender=OrganizationConfigSettings,
        dispatch_uid="invalidate_org_config_cache_on_org_config_delete",
    )
