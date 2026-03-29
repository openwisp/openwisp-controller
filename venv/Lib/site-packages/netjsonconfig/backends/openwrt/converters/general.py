from ..timezones import timezones, timezones_reversed
from .base import OpenWrtConverter


class General(OpenWrtConverter):
    netjson_key = "general"
    intermediate_key = "system"
    _uci_types = ["system"]

    def to_intermediate_loop(self, block, result, index=None):
        network = self.__intermediate_ula(block)
        system = self.__intermediate_system(block)
        if system:
            result["system"] = system
        if network:
            result["network"] = network
        return result

    def __intermediate_system(self, general):
        if not general:
            return None
        general.update(
            {
                ".type": "system",
                ".name": general.pop("id", "system"),
                "hostname": general.get("hostname", "OpenWRT"),
            }
        )
        if "timezone" in general:
            general["zonename"] = general["timezone"]
            general["timezone"] = timezones[general["timezone"]]
        return [self.sorted_dict(general)]

    def __intermediate_ula(self, general):
        if "ula_prefix" in general:
            ula = {
                ".type": "globals",
                ".name": general.pop("globals_id", "globals"),
                "ula_prefix": general.pop("ula_prefix"),
            }
            return [self.sorted_dict(ula)]
        return None

    def to_netjson_loop(self, block, result, index):
        result["general"] = self.__netjson_system(block)
        return result

    def __netjson_system(self, system):
        del system[".type"]
        _name = system.pop(".name")
        if _name != "system":
            system["id"] = _name
        hostname = system.pop("hostname", None)
        zonename = system.pop("zonename", None)
        timezone = system.pop("timezone", None)
        netjson_timezone = None
        if zonename:
            netjson_timezone = zonename
        elif timezone:
            netjson_timezone = timezones_reversed[timezone]
        # set general
        if hostname:
            system["hostname"] = hostname
        if netjson_timezone:
            system["timezone"] = netjson_timezone
        return system
