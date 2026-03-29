from ..wireguard.wireguard import Wireguard
from .schema import schema


class VxlanWireguard(Wireguard):
    schema = schema

    @classmethod
    def auto_client(cls, vni=0, server_ip_address="", vxlan=None, **kwargs):
        """
        Returns a configuration dictionary representing VXLAN configuration
        that is compatible with the passed server configuration.

        :param vni: Virtual Network Identifier
        :param server_ip_address: server internal tunnel address
        :returns: dictionary representing VXLAN properties
        """
        vxlan = vxlan or {}
        config = {
            "server_ip_address": server_ip_address,
            "vni": vni,
            "name": vxlan.get("name", "vxlan"),
        }
        return config
