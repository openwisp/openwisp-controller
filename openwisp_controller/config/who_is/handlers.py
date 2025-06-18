from django.db.models.signals import post_delete, post_save
from swapper import load_model

from .. import settings as app_settings


def connect_who_is_handlers():
    # if WHO_IS_CONFIGURED is False, we do not connect the handlers
    # and return early
    if not app_settings.WHO_IS_CONFIGURED:
        return

    Device = load_model("config", "Device")
    WhoIsInfo = load_model("config", "WhoIsInfo")
    OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")

    post_delete.connect(
        WhoIsInfo.device_who_is_info_delete_handler,
        sender=Device,
        dispatch_uid="device.delete_who_is_info",
    )
    post_save.connect(
        WhoIsInfo.invalidate_org_settings_cache,
        sender=OrganizationConfigSettings,
        dispatch_uid="invalidate_org_config_cache_on_org_config_save",
    )
    post_delete.connect(
        WhoIsInfo.invalidate_org_settings_cache,
        sender=OrganizationConfigSettings,
        dispatch_uid="invalidate_org_config_cache_on_org_config_delete",
    )
