from ..schema import schema
from .base import OpenWrtConverter


class Led(OpenWrtConverter):
    netjson_key = "led"
    intermediate_key = "system"
    _uci_types = ["led"]
    _schema = schema["properties"]["led"]["items"]

    def to_intermediate_loop(self, block, result, index=None):
        block.update(
            {
                ".type": "led",
                ".name": block.pop("id", None) or self.__get_auto_name(block),
            }
        )
        result.setdefault("system", [])
        result["system"].append(self.sorted_dict(block))
        return result

    def __get_auto_name(self, led):
        return "led_{0}".format(led["name"].lower())

    def to_netjson_loop(self, block, result, index):
        result.setdefault("led", [])
        result["led"].append(self.__netjson_led(block))
        return result

    def __netjson_led(self, led):
        del led[".type"]
        _name = led.pop(".name")
        if _name != self.__get_auto_name(led):
            led["id"] = _name
        return self.type_cast(led)
