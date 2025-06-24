from django.db.models.signals import post_delete, post_save
from swapper import load_model

from ..tests.utils import CreateConfigMixin

Device = load_model("config", "Device")
WhoIsInfo = load_model("config", "WhoIsInfo")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")


class CreateWhoIsMixin(CreateConfigMixin):
    def _create_whois_info(self, **kwargs):
        options = dict(
            ip_address="172.217.22.14",
            address={
                "city": "Mountain View",
                "country": "United States",
                "continent": "North America",
                "postal": "94043",
            },
            asn="15169",
            isp="Google LLC",
            timezone="America/Los_Angeles",
            cidr="172.217.22.0/24",
        )

        options.update(kwargs)
        w = WhoIsInfo(**options)
        w.full_clean()
        w.save()
        return w

    # Signals are connected when apps are loaded,
    # and if WHOIS is Configured all related WHOIS
    # handlers are also connected. Thus we need to
    # disconnect them.
    def _disconnect_signals(self):
        post_delete.disconnect(
            WhoIsInfo.device_whois_info_delete_handler,
            sender=Device,
            dispatch_uid="device.delete_whois_info",
        )
        post_save.disconnect(
            WhoIsInfo.invalidate_org_settings_cache,
            sender=OrganizationConfigSettings,
            dispatch_uid="invalidate_org_config_cache_on_org_config_save",
        )
        post_delete.disconnect(
            WhoIsInfo.invalidate_org_settings_cache,
            sender=OrganizationConfigSettings,
            dispatch_uid="invalidate_org_config_cache_on_org_config_delete",
        )
