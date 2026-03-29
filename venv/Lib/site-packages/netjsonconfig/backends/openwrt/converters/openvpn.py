from ...openvpn.converters import OpenVpn as BaseOpenVpn
from .base import OpenWrtConverter


class OpenVpn(OpenWrtConverter, BaseOpenVpn):
    _uci_types = ["openvpn"]

    def __intermediate_vpn(self, vpn):
        if vpn.get("fragment") == 0:
            del vpn["fragment"]
        vpn.update(
            {
                ".name": self._get_uci_name(vpn.pop("name")),
                ".type": "openvpn",
                "enabled": not vpn.pop("disabled", False),
            }
        )
        if (ciphers := vpn.get("tls_cipher")) and isinstance(ciphers, str):
            vpn["tls_cipher"] = []
            # only add non empty strings
            for part in ciphers.split(":"):
                if part:
                    vpn["tls_cipher"].append(part)
        return super().__intermediate_vpn(vpn, remove=[""])

    def __netjson_vpn(self, vpn):
        if vpn.get("server_bridge") == "1":
            vpn["server_bridge"] = ""
        # 'disabled' defaults to False in OpenWRT
        vpn["disabled"] = vpn.pop("enabled", "0") == "0"
        vpn["name"] = vpn.pop(".name")
        del vpn[".type"]
        if (ciphers := vpn.get("tls_cipher")) and isinstance(ciphers, list) and ciphers:
            vpn["tls_cipher"] = ":".join(ciphers)
        return super().__netjson_vpn(vpn)
