from ..schema import schema
from .base import OpenWrtConverter


class Switch(OpenWrtConverter):
    netjson_key = "switch"
    intermediate_key = "network"
    _uci_types = ["switch", "switch_vlan"]
    _switch_schema = schema["properties"]["switch"]["items"]
    _vlan_schema = schema["properties"]["switch"]["items"]["properties"]["vlan"][
        "items"
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # instance attributes used during backward conversion
        self._vlan_counter = 0
        self._switch_map = {}

    def to_intermediate_loop(self, block, result, index=None):
        switch_vlan = self.__intermediate_switch(block)
        result.setdefault("network", [])
        result["network"] += switch_vlan
        return result

    def to_netjson_clean(self, intermediate_data):
        reordered_data, last_items = [], []
        for block in super().to_netjson_clean(intermediate_data):
            if ".type" in block and block[".type"] == "switch_vlan":
                last_items.append(block)
            else:
                reordered_data.append(block)
        reordered_data.extend(last_items)
        return reordered_data

    def __intermediate_switch(self, switch):
        switch.update(
            {".type": "switch", ".name": switch.pop("id", None) or switch["name"]}
        )
        i = 1
        vlans = []
        for vlan in switch["vlan"]:
            vlan.update(
                {
                    ".type": "switch_vlan",
                    ".name": vlan.pop("id", None)
                    or self.__get_auto_name(switch["name"], i),
                }
            )
            if "vid" not in vlan:
                vlan["vid"] = vlan["vlan"]
            vlans.append(self.sorted_dict(vlan))
            i += 1
        del switch["vlan"]
        return [self.sorted_dict(switch)] + vlans

    def __get_auto_name(self, name, i):
        return "{0}_vlan{1}".format(name, i)

    def to_netjson_loop(self, block, result, index):
        _name = block.pop(".name")
        _type = block.pop(".type")
        result.setdefault("switch", [])
        if _type == "switch":
            self._vlan_counter = 0
            # set id attribute only if name option
            # and UCI identifier differ
            if _name != block["name"]:
                block["id"] = _name
            switch = self.type_cast(block, self._switch_schema)
            self._switch_map[switch["name"]] = switch
            result["switch"].append(switch)
        else:
            self._vlan_counter += 1
            # set id attribute only if name option
            # and expected UCI identifier differ
            if _name != self.__get_auto_name(block["device"], self._vlan_counter):
                block["id"] = _name
            vlan = self.type_cast(block, self._vlan_schema)
            vlan = self.__netjson_vid(vlan)
            # appends vlan to the corresponding switch
            self._switch_map[vlan["device"]].setdefault("vlan", [])
            self._switch_map[vlan["device"]]["vlan"].append(vlan)
        return result

    def __netjson_vid(self, vlan):
        if "vid" in vlan:
            vlan["vid"] = int(vlan["vid"])
            if vlan["vid"] == vlan["vlan"]:
                del vlan["vid"]
        else:
            vlan["vid"] = None
        return vlan
