from ..base.converter import BaseConverter
from .schema import schema


class ZeroTier(BaseConverter):
    netjson_key = "zerotier"
    intermediate_key = "zerotier"
    _schema = schema["definitions"]["zerotier_server"]

    def to_intermediate_loop(self, block, result, index=None):
        vpn = self.__intermediate_vpn(block)
        result.setdefault("zerotier", [])
        result["zerotier"].append(vpn)
        return result

    def __intermediate_vpn(self, config, remove=None):
        config.pop("client_options", None)
        return self.sorted_dict(config)

    def to_netjson_loop(self, block, result, index=None):
        vpn = self.__netjson_vpn(block)
        result.setdefault("zerotier", [])
        result["zerotier"].append(vpn)
        return result

    def __netjson_vpn(self, vpn):
        vpn = self.type_cast(vpn, self._schema)
        return vpn
