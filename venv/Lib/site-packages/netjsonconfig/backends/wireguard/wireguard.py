from ..base.backend import BaseVpnBackend
from . import converters
from .parser import config_suffix, vpn_pattern
from .renderer import WireguardRenderer
from .schema import schema


class Wireguard(BaseVpnBackend):
    schema = schema
    converters = [converters.Wireguard]
    renderer = WireguardRenderer
    # BaseVpnBackend attributes
    vpn_pattern = vpn_pattern
    config_suffix = config_suffix

    @classmethod
    def auto_client(cls, host="", public_key="", server={}, port=51820, **kwargs):
        """
        Returns a configuration dictionary representing Wireguard configuration
        that is compatible with the passed server configuration.

        :param host: remote VPN server
        :param port: listen port for Wireguard Client
        :param server: dictionary representing a single Wireguard server configuration
        :param public_key: public key of the Wireguard server
        :returns: dictionary representing a Wireguard server and client properties
        """
        return {
            "interface_name": server.get("name", ""),
            "client": {
                "port": port,
                "private_key": kwargs.get("private_key", "{{private_key}}"),
                "ip_address": kwargs.get("ip_address"),
            },
            "server": {
                "public_key": public_key,
                "endpoint_host": host,
                "endpoint_port": server.get("port", 51820),
                "allowed_ips": [kwargs.get("server_ip_network", "")],
            },
        }
