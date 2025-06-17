from django.db.models.signals import post_delete, post_save
from swapper import load_model


def connect_who_is_handlers():
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
