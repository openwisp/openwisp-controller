from ipaddress import ip_interface

from ..schema import schema
from .base import OpenWrtConverter


class Routes(OpenWrtConverter):
    netjson_key = "routes"
    intermediate_key = "network"
    _uci_types = ["route", "route6"]

    def to_intermediate_loop(self, block, result, index=None):
        route = self.__intermediate_route(block, index)
        result.setdefault("network", [])
        result["network"].append(route)
        return result

    def __intermediate_route(self, route, index):
        network = ip_interface(route.pop("destination"))
        target = network.ip if network.version == 4 else network.network
        route.update(
            {
                ".type": "route{0}".format("6" if network.version == 6 else ""),
                ".name": route.pop("name", None) or self.__get_auto_name(index),
                "interface": route.pop("device"),
                "target": str(target),
                "gateway": route.pop("next"),
                "metric": route.pop("cost"),
            }
        )
        if network.version == 4:
            route["netmask"] = str(network.netmask)
        return self.sorted_dict(route)

    def __get_auto_name(self, i):
        return "route{0}".format(i)

    def to_netjson_loop(self, block, result, index):
        rule = self.__netjson_route(block, index)
        result.setdefault("routes", [])
        result["routes"].append(rule)
        return result

    _schema = schema["properties"]["routes"]["items"]

    def __netjson_route(self, route, i):
        _name = route.pop(".name")
        if _name != self.__get_auto_name(i):
            route["name"] = _name
        network = route.pop("target")
        if "netmask" in route:
            network = "{0}/{1}".format(network, route.pop("netmask"))
        route.update(
            {
                "device": route.pop("interface"),
                "destination": str(ip_interface(network)),
                "next": route.pop("gateway", ""),
                "cost": route.pop(
                    "metric", self._schema["properties"]["cost"]["default"]
                ),
            }
        )
        del route[".type"]
        return self.type_cast(route)
