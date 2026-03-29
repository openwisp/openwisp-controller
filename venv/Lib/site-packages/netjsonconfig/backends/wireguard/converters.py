from ..base.converter import BaseConverter
from .schema import schema


class Wireguard(BaseConverter):
    netjson_key = "wireguard"
    intermediate_key = "wireguard"
    _schema = schema
    _forward_property_map = {
        "port": "ListenPort",
        "private_key": "PrivateKey",
        "address": "Address",
        "dns": "DNS",
        "mtu": "MTU",
        "save_config": "SaveConfig",
        "table": "Table",
        "pre_up": "PreUp",
        "post_up": "PostUp",
        "pre_down": "PreDown",
        "post_down": "PostDown",
    }

    def to_intermediate_loop(self, block, result, index=None):
        vpn = self.__intermediate_vpn(block)
        result.setdefault("wireguard", [])
        result["wireguard"].append(vpn)
        return result

    def __intermediate_vpn(self, config, remove=None):
        # Required properties
        for option in ["port", "private_key", "address"]:
            config[self._forward_property_map[option]] = config.pop(option)
        # Optional properties
        for option in self._forward_property_map.keys():
            if option in ["port", "private_key", "address"]:
                # These options have been already handled
                continue
            if config.get(option, None) not in ["", None, []]:
                if option == "dns":
                    config[option] = ",".join(config[option])
                elif option == "save_config":
                    config[option] = "true" if config[option] else "false"
                config[self._forward_property_map[option]] = config.pop(option)
            else:
                config.pop(option, None)
        config["peers"] = self.__intermediate_peers(config.get("peers", []))
        return self.sorted_dict(config)

    def __intermediate_peers(self, peers):
        peer_list = []
        for peer in peers:
            peer["AllowedIPs"] = peer.pop("allowed_ips")
            peer["PublicKey"] = peer.pop("public_key")
            peer["PreSharedKey"] = peer.pop("preshared_key", None)
            host = peer.pop("endpoint_host", None)
            port = peer.pop("endpoint_port", None)
            if host and port:
                peer["Endpoint"] = f"{host}:{port}"
            peer_list.append(self.sorted_dict(peer))
        return peer_list
