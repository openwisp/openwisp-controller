from ...zerotier.converters import ZeroTier as BaseZeroTier
from ..schema import schema
from .base import OpenWrtConverter


class ZeroTier(OpenWrtConverter, BaseZeroTier):
    _uci_types = ["zerotier", "network"]
    _schema = schema["properties"]["zerotier"]["items"]

    def to_intermediate_loop(self, block, result, index=None):
        vpn = self.__intermediate_vpn(block)
        networks = vpn.pop("networks")
        result.setdefault("zerotier", [])
        result["zerotier"].append(vpn)
        for network in networks:
            result["zerotier"].append(self.__intermediate_network(network))
        return result

    def __intermediate_vpn(self, vpn):
        nwid_ifnames = vpn.get("networks", [])
        files = self.netjson.get("files", [])
        self.netjson["files"] = self.__get_zt_ifname_files(vpn, files)
        vpn.update(
            {
                ".name": self._get_uci_name(vpn.pop("name")),
                ".type": "zerotier",
                "config_path": vpn.get("config_path", "/etc/openwisp/zerotier"),
                "copy_config_path": vpn.get("copy_config_path", "1"),
                "join": [networks.get("id", "") for networks in nwid_ifnames],
                "enabled": not vpn.pop("disabled", False),
            }
        )
        if vpn.get("local_conf"):
            vpn["local_conf_path"] = vpn.get("local_conf")
        elif vpn.get("local_conf_path"):
            vpn["local_conf"] = vpn.get("local_conf_path")
        return super().__intermediate_vpn(vpn, remove=[""])

    def __intermediate_network(self, network):
        # Generates configuration for ZeroTier > 1.14
        # where networks are defined in individual blocks.
        network.update(
            {
                ".name": self._get_uci_name(network.pop("ifname")),
                ".type": "network",
            }
        )
        return self.sorted_dict(network)

    def to_netjson_loop(self, block, result, index=None):
        if block.get(".type") == "zerotier":
            vpn = self.__netjson_vpn(block)
            result.setdefault("zerotier", [])
            result["zerotier"].append(vpn)
        else:
            # Handles ZeroTier > 1.14 configuration where
            # networks are defined in individual blocks.
            network = self.__netjson_network(block)
            result["zerotier"][0]["networks"].append(network)
        return result

    def __netjson_vpn(self, vpn):
        vpn["name"] = vpn.pop(".name")
        # 'disabled' defaults to False in OpenWRT
        vpn["disabled"] = vpn.pop("enabled", "0") == "0"
        del vpn[".type"]
        # Handles ZeroTier < 1.14 configuration where networks were present
        # in the zerotier block.
        nwids = vpn.pop("join", [])
        vpn["networks"] = [
            {"id": nwid, "ifname": self._get_ifname_from_id(nwid)} for nwid in nwids
        ]
        if "local_conf" in vpn:
            vpn["local_conf_path"] = vpn.pop("local_conf")
        return super().__netjson_vpn(vpn)

    def __netjson_network(self, network):
        for key in [".name", ".type"]:
            network.pop(key)
        network["ifname"] = self._get_ifname_from_id(network["id"])
        # Handle boolean fields
        if "allow_global" in network:
            network["allow_global"] = network["allow_global"] == "1"
        if "allow_default" in network:
            network["allow_default"] = network["allow_default"] == "1"
        if "allow_dns" in network:
            network["allow_dns"] = network["allow_dns"] == "1"
        if "allow_managed" in network:
            network["allow_managed"] = network["allow_managed"] == "1"
        return network

    def _get_ifname_from_id(self, network_id):
        return f"owzt{network_id[-6:]}"

    def __get_zt_ifname_files(self, vpn, files):
        config_path = vpn.get("config_path", "/etc/openwisp/zerotier")
        nwid_ifnames = vpn.get("networks", [])
        zt_file_contents = "# network_id=interface_name\n"

        for networks in nwid_ifnames:
            nwid = networks.get("id", "")
            ifname = networks.get("ifname")
            zt_file_contents += f"{nwid}={ifname}\n"

        zt_interface_map = {
            "path": f"{config_path}/devicemap",
            "mode": "0644",
            "contents": zt_file_contents,
        }

        if not files:
            return [zt_interface_map]
        updated_files = []
        for file in files:
            if file.get("path") == zt_interface_map.get("path"):
                zt_interface_map["contents"] += "\n" + file["contents"]
            else:
                updated_files.append(file)
        if zt_interface_map.get("contents"):
            updated_files.append(zt_interface_map)
        return updated_files
