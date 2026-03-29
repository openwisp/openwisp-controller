from ipaddress import ip_network

from ..schema import schema
from .base import OpenWrtConverter


class Rules(OpenWrtConverter):
    netjson_key = "ip_rules"
    intermediate_key = "network"
    _uci_types = ["rule", "rule6"]
    _schema = schema["properties"]["ip_rules"]["items"]

    def to_intermediate_loop(self, block, result, index=None):
        rule = self.__intermediate_rule(block, index)
        result.setdefault("network", [])
        result["network"].append(rule)
        return result

    def __intermediate_rule(self, rule, index):
        src_net = None
        dest_net = None
        family = 4
        if "src" in rule:
            src_net = ip_network(rule["src"])
        if "dest" in rule:
            dest_net = ip_network(rule["dest"])
        if dest_net or src_net:
            family = dest_net.version if dest_net else src_net.version
        rule.update(
            {
                ".type": "rule{0}".format(family).replace("4", ""),
                ".name": rule.pop("name", None) or self.__get_auto_name(index),
            }
        )
        return self.sorted_dict(rule)

    def __get_auto_name(self, i):
        return "rule{0}".format(i)

    def to_netjson_loop(self, block, result, index):
        rule = self.__netjson_rule(block, index)
        result.setdefault("ip_rules", [])
        result["ip_rules"].append(rule)
        return result

    def __netjson_rule(self, rule, i):
        _name = rule.pop(".name")
        if _name != self.__get_auto_name(i):
            rule["name"] = _name
        del rule[".type"]
        return self.type_cast(rule)
