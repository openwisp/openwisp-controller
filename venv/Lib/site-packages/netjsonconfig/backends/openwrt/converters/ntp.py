from ..schema import schema
from .base import OpenWrtConverter


class Ntp(OpenWrtConverter):
    netjson_key = "ntp"
    intermediate_key = "system"
    _uci_types = ["timeserver"]
    _schema = schema["properties"]["ntp"]

    def to_intermediate_loop(self, block, result, index=None):
        if block:
            block.update({".type": "timeserver", ".name": block.pop("id", "ntp")})
            result.setdefault("system", [])
            result["system"] = [self.sorted_dict(block)]
        return result

    def to_netjson_loop(self, block, result, index):
        result["ntp"] = self.__netjson_ntp(block)
        return result

    def __netjson_ntp(self, ntp):
        del ntp[".type"]
        _name = ntp.pop(".name")
        if _name != "ntp":
            ntp["id"] = _name
        return self.type_cast(ntp)
