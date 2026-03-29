from ..base.backend import BaseVpnBackend
from . import converters
from .parser import ZeroTierParser, config_suffix, vpn_pattern
from .renderer import ZeroTierRenderer
from .schema import schema


class ZeroTier(BaseVpnBackend):
    schema = schema
    converters = [converters.ZeroTier]
    renderer = ZeroTierRenderer
    parser = ZeroTierParser
    # BaseVpnBackend attributes
    vpn_pattern = vpn_pattern
    config_suffix = config_suffix

    @classmethod
    def auto_client(
        cls,
        name="global",
        networks=None,
        identity_secret="{{secret}}",
        config_path="/etc/openwisp/zerotier",
        disabled=False,
        client_options=None,
    ):
        networks = networks or []
        client_options = client_options or {}
        for network in networks:
            network.update(client_options)
        return {
            "name": name,
            "networks": networks,
            "secret": identity_secret,
            "config_path": config_path,
            "disabled": disabled,
        }
