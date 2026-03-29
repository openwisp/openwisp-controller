from collections import OrderedDict
from copy import deepcopy
from ipaddress import ip_address, ip_interface

from ....utils import merge_list
from ..schema import schema
from .base import OpenWrtConverter


class Interfaces(OpenWrtConverter):
    netjson_key = "interfaces"
    intermediate_key = "network"
    _uci_types = ["interface", "globals"]
    _bridge_interface_options = {
        "stp": [
            "stp",
            "forward_delay",
            "hello_time",
            "priority",
            "ageing_time",
            "max_age",
        ],
        "igmp_snooping": [
            "igmp_snooping",
            "multicast_querier",
            "query_interval",
            "query_response_interval",
            "last_member_interval",
            "hash_max",
            "robustness",
        ],
        "all": ["vlan_filtering", "macaddr", "mtu"],
    }
    _custom_protocols = ["ppp"]
    _interface_dsa_types = [
        "loopback",
        "ethernet",
        "bridge",
        "wireless",
        "8021q",
        "8021ad",
    ]

    def __init__(self, backend):
        super().__init__(backend)
        self._device_config = {}
        self._bridge_vlan_config_uci = []

    def __set_dsa_interface(self, interface):
        """
        sets dsa interface property to manage new syntax introduced
        in OpenWrt 21.02 by checking supported types and protocols
        """
        self.dsa_interface = (
            self.dsa
            and interface.get("proto", None) not in self._custom_protocols
            and interface.get("type", None) in self._interface_dsa_types
            and interface.get("ifname", interface.get("device"))
            not in self._bridge_vlan_config_uci
        )

    def to_intermediate_loop(self, block, result, index=None):
        uci_name = self._get_uci_name(block.get("network") or block["name"])
        address_list = self.__intermediate_addresses(block)
        interface = self.__intermediate_interface(block, uci_name)
        self.__set_dsa_interface(interface)
        if self.dsa_interface:
            vlan_list = interface.pop("vlan_filtering", [])
            if vlan_list:
                interface["vlan_filtering"] = True
            uci_device = self.__intermediate_device(interface, address_list)
            if uci_device:
                result.setdefault("network", [])
                result["network"].append(self.sorted_dict(uci_device))
            uci_vlan_interfaces = []
            for vlan in vlan_list:
                uci_vlan, uci_vlan_interface = self.__intermediate_vlan(
                    uci_name, interface, vlan
                )
                result["network"].append(self.sorted_dict(uci_vlan))
                uci_vlan_interfaces.append(uci_vlan_interface)
            for uci_interface in uci_vlan_interfaces:
                result["network"].append(self.sorted_dict(uci_interface))
        # create one or more "config interface" UCI blocks
        i = 1
        for address in address_list:
            uci_interface = deepcopy(interface)
            # add suffix to logical name when
            # there is more than one interface
            if i > 1:
                uci_interface[".name"] = "{name}_{i}".format(name=uci_name, i=i)
            uci_interface.update(
                {
                    "dns": self.__intermediate_dns_servers(uci_interface, address),
                    "dns_search": self.__intermediate_dns_search(
                        uci_interface, address
                    ),
                    "proto": self.__intermediate_proto(uci_interface, address),
                }
            )
            uci_interface = self.__intermediate_bridge(uci_interface, i)
            if address:
                uci_interface.update(address)
            result.setdefault("network", [])
            # Use merge_list instead of appending the interface directly
            # to allow users to override the auto-generated interface
            # (e.g., when using VLAN filtering on a bridge).
            result["network"] = merge_list(
                result["network"],
                [self.sorted_dict(uci_interface)],
                identifiers=[".name", ".type"],
            )
            i += 1
        return result

    def __intermediate_addresses(self, interface):
        """
        converts NetJSON address to
        UCI intermediate data structure
        """
        # wireguard interfaces need a different format
        if interface.get("type") == "wireguard":
            return self.__intermediate_wireguard_addresses(interface)
        address_list = self.get_copy(interface, "addresses")
        # ignore wireless interfaces without addresses
        if not address_list and interface["type"] == "wireless":
            return []
        # do not ignore interfaces if they do not contain any address
        if not address_list:
            return [{"proto": "none"}]
        result = []
        static = {}
        dhcp = []
        for address in address_list:
            family = address.get("family")
            # dhcp
            if address["proto"] == "dhcp":
                address["proto"] = "dhcp" if family == "ipv4" else "dhcpv6"
                dhcp.append(self.__intermediate_address(address))
                continue
            if "gateway" in address:
                uci_key = "gateway" if family == "ipv4" else "ip6gw"
                interface[uci_key] = address["gateway"]
            # static
            address_key = "ipaddr" if family == "ipv4" else "ip6addr"
            static.setdefault(address_key, [])
            static[address_key].append("{address}/{mask}".format(**address))
            static.update(self.__intermediate_address(address))
        if static:
            result.append(self.__intermediate_static_address(static))
        if dhcp:
            result += dhcp
        return result

    def __intermediate_static_address(self, uci):
        # do not use CIDR notation when using a single ipv4
        # see https://github.com/openwisp/netjsonconfig/issues/54
        if len(uci.get("ipaddr", [])) == 1:
            network = ip_interface(uci["ipaddr"][0])
            uci["ipaddr"] = str(network.ip)
            uci["netmask"] = str(network.netmask)
        # do not use lists when using a single ipv6 address
        # (avoids to change output of existing configuration)
        if len(uci.get("ip6addr", [])) == 1:
            uci["ip6addr"] = uci["ip6addr"][0]
        return uci

    def __intermediate_wireguard_addresses(self, interface):
        addresses = interface.pop("addresses")
        address_list = []
        for address_dict in addresses:
            address = address_dict["address"]
            if "mask" in address_dict:
                address = f'{address}/{address_dict["mask"]}'
            address_list.append(address)
        static = {"addresses": address_list, "proto": "wireguard"}
        return [static]

    def __intermediate_interface(self, interface, uci_name):
        """
        converts NetJSON interface to
        UCI intermediate data structure
        """
        interface.update({".type": "interface", ".name": uci_name})
        interface["ifname"] = interface.pop("name")
        if "mac" in interface:
            # mac address of wireless interface must
            # be set in /etc/config/wireless, therfore
            # we can skip this in /etc/config/network
            if interface.get("type") != "wireless":
                interface["macaddr"] = interface["mac"]
            del interface["mac"]
        if "autostart" in interface:
            interface["auto"] = interface["autostart"]
            del interface["autostart"]
        if "disabled" in interface:
            interface["enabled"] = not interface["disabled"]
            del interface["disabled"]
        if "wireless" in interface:
            del interface["wireless"]
        if "addresses" in interface:
            del interface["addresses"]
        # specific transformation
        type_ = self._get_uci_name(interface["type"])
        method = getattr(self, f"_intermediate_{type_}", None)
        if method:
            interface = method(interface)
        self._check_bridge_vlan(interface)
        if "network" in interface:
            del interface["network"]
        return interface

    def _check_bridge_vlan(self, interface):
        if self.dsa:
            if (
                "." in interface.get("ifname", "")
                and interface["ifname"] in self._bridge_vlan_config_uci
            ):
                # Cleans L2 options from the interface
                self._add_l2_options({}, interface)
                interface["device"] = interface.pop("ifname")
        return interface

    def _intermediate_modem_manager(self, interface):
        interface["proto"] = "modemmanager"
        interface["pincode"] = interface.pop("pin", None)
        return interface

    def _intermediate_wireguard(self, interface):
        interface["proto"] = "wireguard"
        interface["listen_port"] = interface.pop("port", None)
        del interface["ifname"]
        return interface

    def _intermediate_vxlan(self, interface):
        interface["proto"] = "vxlan"
        interface["peeraddr"] = interface.pop("vtep")
        interface["vid"] = interface.pop("vni")
        return interface

    def _intermediate_8021_vlan(self, interface):
        interface["name"] = "{}.{}".format(interface["ifname"], interface["vid"])
        interface[".name"] = interface.get("network") or "vlan_{}_{}".format(
            interface[".name"], interface["vid"]
        )
        return interface

    def _intermediate_8021q(self, interface):
        return self._intermediate_8021_vlan(interface)

    def _intermediate_8021ad(self, interface):
        return self._intermediate_8021_vlan(interface)

    _address_keys = ["address", "mask", "family", "gateway"]

    def __intermediate_address(self, address):
        """
        deletes NetJSON address keys
        """
        for key in self._address_keys:
            if key in address:
                del address[key]
        return address

    def __intermediate_vlan(self, uci_name, interface, vlan):
        vid = vlan["vlan"]
        uci_vlan = {
            ".type": "bridge-vlan",
            ".name": f"{uci_name}_{vid}",
            "vlan": vid,
            "device": interface["ifname"],
        }
        uci_vlan[".name"] = "vlan_{}".format(uci_vlan[".name"])
        uci_vlan_interface = {
            ".type": "interface",
            # To avoid conflicts, auto-generated interfaces are prefixed with "if"
            # because UCI does not support multiple blocks with the same name.
            ".name": f"{uci_name}_{vid}",
            "device": "{ifname}.{vid}".format(ifname=interface["ifname"], vid=vid),
            "proto": "none",
        }
        if "ports" in vlan:
            uci_vlan["ports"] = []
            for port in vlan.get("ports"):
                tagging = ""
                pvid = ""
                if port.get("tagging"):
                    tagging = ":{tagging}".format(tagging=port["tagging"])
                if port.get("primary_vid"):
                    pvid = "*"
                uci_vlan["ports"].append(
                    "{ifname}{tagging}{pvid}".format(
                        ifname=port["ifname"], tagging=tagging, pvid=pvid
                    )
                )
        self._bridge_vlan_config_uci.append(uci_vlan_interface["device"])
        return uci_vlan, uci_vlan_interface

    def __intermediate_device(self, interface, address_list):
        """
        Converts NetJSON bridge to intermediate
        data structure compatible with new syntax
        introduced in OpenWrt 21.02.
        """
        device = {}
        # Add L2 options (needed for > OpenWrt 21.02)
        self._add_l2_options(device, interface)
        base = {
            ".type": "device",
            ".name": "device_{}".format(interface[".name"]),
            "name": interface["ifname"],
        }
        device.update(base)

        # Add 'device' option in related interface configuration
        if not interface.get("device", None):
            interface["device"] = device["name"]
        interface_type = interface["type"]
        if interface_type.startswith("8021"):
            device.update(
                {
                    "type": interface["type"],
                    "vid": interface.pop("vid"),
                    "name": interface.pop("name"),
                    ".name": "device_{}".format(interface[".name"].lstrip("vlan_")),
                    "ifname": interface.pop("ifname"),
                    "ingress_qos_mapping": interface.pop("ingress_qos_mapping", []),
                    "egress_qos_mapping": interface.pop("egress_qos_mapping", []),
                }
            )
            interface["device"] = device["name"]
        if interface_type != "bridge":
            # A non-bridge interface that contains L2 options.
            if device == base:
                return {}
            return device
        device["type"] = "bridge"
        if not interface["ifname"].startswith("br-"):
            # Add "br-" prefix to the bridge name
            # for backward compatibility: OpenWrt <= 19
            # automatically added the "br-" prefix to bridges,
            # but later in OpenWrt 21 the bridge logic changed
            # and that is no longer true, for that reason
            # old configurations of OpenWISP made for OpenWrt 19
            # which relied on the bridge names to be prefixed
            # automatically with "br-" were breaking;
            # to resolve this backward compatibility issue
            # we now add the "br-" prefix automatically if needed.
            interface["ifname"] = f'br-{interface["ifname"]}'
        device["name"] = interface["ifname"]
        interface["device"] = device["name"]

        # Add STP options only if STP is enabled
        self._add_options(
            "stp", self._bridge_interface_options["stp"], device, interface
        )
        # Add IGMP snooping options only if IGMP snooping is enabled
        self._add_options(
            "igmp_snooping",
            self._bridge_interface_options["igmp_snooping"],
            device,
            interface,
        )
        device_options = (
            self._bridge_interface_options["all"]
            + self._bridge_interface_options["stp"]
            + self._bridge_interface_options["igmp_snooping"]
        )
        for option in device_options:
            if option in interface:
                device[option] = interface.pop(option, None)
        device["ports"] = interface.get("bridge_members", [])
        if device["ports"] == []:
            device["bridge_empty"] = True
            del device["ports"]
        return self.sorted_dict(device)

    @staticmethod
    def _add_options(property_name, property_options, device, interface):
        if interface.get(property_name, False):
            device[property_name] = True
            for option in property_options:
                if interface.get(option):
                    device[option] = interface[option]

    @staticmethod
    def _add_l2_options(device, interface):
        l2_options = [
            "rpfilter",
            "txqueuelen",
            "neighreachabletime",
            "neighgcstaletime",
            "neighlocktime",
            "igmpversion",
            "mldversion",
            "promisc",
            "acceptlocal",
            "sendredirects",
            "multicast",
            "mtu",
            "mtu6",
            "dadtransmits",
        ]
        for option in l2_options:
            if option in interface:
                device[option] = interface.pop(option)
        if interface.get("macaddr", None):
            device["macaddr"] = interface.pop("macaddr")

    def __clean_intermediate_bridge(self, interface):
        """
        Removes options that are not required in the configuration.
        """
        if self.dsa_interface:
            repeated_options = (
                ["ifname", "type", "bridge_members"]
                + self._bridge_interface_options["stp"]
                + self._bridge_interface_options["igmp_snooping"]
                + self._bridge_interface_options["all"]
            )
            for attr in repeated_options:
                if attr in interface:
                    del interface[attr]

    def __intermediate_bridge(self, interface, i):
        """
        converts NetJSON bridge to
        UCI intermediate data structure
        """
        # ensure type "bridge" is only given to one logical interface
        if interface["type"] == "bridge" and i < 2:
            bridge_members = " ".join(interface.pop("bridge_members"))
            if self.dsa_interface:
                interface["device"] = interface["ifname"]
            else:
                if bridge_members:
                    interface["ifname"] = bridge_members
                # if no members, this is an empty bridge
                else:
                    interface["bridge_empty"] = True
                    del interface["ifname"]
        # bridge has already been defined
        # but we need to add more references to it
        elif interface["type"] == "bridge" and i >= 2:
            # openwrt adds "br-" prefix to bridge interfaces
            # we need to take this into account when referring
            # to these physical names
            if "br-" not in interface["ifname"]:
                interface["ifname"] = "br-{ifname}".format(**interface)
            # do not repeat bridge attributes (they have already been processed)
            repeated_options = (
                ["type", "bridge_members", "gateway"]
                + self._bridge_interface_options["stp"]
                + self._bridge_interface_options["igmp_snooping"]
            )
            for attr in repeated_options:
                if attr in interface:
                    del interface[attr]
        elif interface["type"] != "bridge":
            del interface["type"]
        self.__clean_intermediate_bridge(interface)
        return interface

    def __intermediate_proto(self, interface, address):
        """
        determines UCI interface "proto" option
        """
        # proto defaults to static
        address_proto = address.pop("proto", "static")
        if "proto" not in interface:
            return address_proto
        else:
            # allow override on interface level
            return interface.pop("proto")

    def __intermediate_dns_servers(self, uci, address):
        """
        determines UCI interface "dns" option
        """
        # allow override
        if "dns" in uci:
            return uci["dns"]
        # ignore if using DHCP or if "proto" is none
        if address["proto"] in ["dhcp", "dhcpv6", "none"]:
            return None
        dns = self.netjson.get("dns_servers", None)
        if dns:
            return " ".join(dns)

    def __intermediate_dns_search(self, uci, address):
        """
        determines UCI interface "dns_search" option
        """
        # allow override
        if "dns_search" in uci:
            return uci["dns_search"]
        # ignore if "proto" is none
        if address["proto"] == "none":
            return None
        dns_search = self.netjson.get("dns_search", None)
        if dns_search:
            return " ".join(dns_search)

    def to_netjson(self, remove_block=True):
        """
        Override the base ``to_netjson`` method to correctly handle
        OpenWrt ≥ 21 (DSA) configurations.

        On OpenWrt < 21 (pre-DSA), each ``interface`` block contained a complete
        description of that interface. Starting with OpenWrt 21 (DSA), key
        settings are split across multiple blocks (``device``, ``bridge-vlan``,
        and ``interface``). This means that individual blocks are no longer
        self-contained and must be parsed in a specific order to produce a
        valid and consistent NetJSON representation.

        Parsing order:
        1. Parse all ``device`` and ``bridge-vlan`` blocks.
        2. Parse ``interface`` blocks not referencing VLAN interfaces.
        3. Add fallback interfaces for any unconsumed ``device_config``.
        4. Parse remaining ``interface`` blocks (including VLAN interfaces).
        """

        result = OrderedDict()
        # Parse device blocks
        result = self.__process_blocks(
            result,
            remove_block,
            self.__skip_non_device_block,
            self.__process_device_block,
        )
        # Parse non VLAN interfaces
        result = self.__process_blocks(result, remove_block, self.__skip_vlan_block)
        # Add fallback interfaces before parsing VLAN interfaces.
        # This ensures that the primary bridge/device interfaces are already present so
        # subsequently parsed VLAN/interface blocks can correctly reference or
        # override them. This preserves the required ordering for producing
        # a consistent NetJSON -> UCI mapping.
        result = self.__add_fallback_interfaces(result)
        # Parse remaining interfaces
        result = self.__process_blocks(result, remove_block, self.should_skip_block)

        return result

    def __is_device_config(self, interface):
        """
        determines if the configuration is a device from NetJSON
        """
        return interface.get("type", None) == "device"

    def __skip_non_device_block(self, block):
        return self.should_skip_block(block) or (
            not block.get("bridge_21", None) and not self.__is_device_config(block)
        )

    def __skip_vlan_block(self, block):
        return self.should_skip_block(block) or (
            block.get("device")
            and "." in block["device"]
            and block["device"].split(".")[0] in self._device_config
        )

    def __process_blocks(self, result, remove_block, skip_fn, handler_fn=None):
        intermediate_data = self.to_netjson_clean(
            self.intermediate_data[self.intermediate_key]
        )
        handler_fn = handler_fn or self.to_netjson_loop
        for index, block in enumerate(list(intermediate_data), start=1):
            if skip_fn(block):
                continue
            if remove_block:
                self.intermediate_data[self.intermediate_key].remove(block)
            result = handler_fn(block, result, index)
        return result

    def __process_device_block(self, block, result, index):
        if block.get("type") == "bridge-vlan":
            device_name = block.get("device")
            if device_name and device_name not in self._device_config:
                self._device_config[device_name] = {}
            self.__netjson_vlan(block, self._device_config[device_name])
        else:
            self.__netjson_device(block)
        return result

    def __add_fallback_interfaces(self, result):
        """Add fallback interfaces for any unconsumed device configs."""

        def make_fallback_interface(name, config):
            interface_name = config.get(".name", name)
            if interface_name.startswith("device_"):
                interface_name = interface_name[7:]  # len("device_") = 7
            return OrderedDict(
                {
                    ".type": "interface",
                    ".name": interface_name,
                    "device": name,
                    "proto": "none",
                }
            )

        index = len(result) + 1
        for name, device_config in self._device_config.copy().items():
            if device_config.get("consumed", False):
                continue
            interface = make_fallback_interface(name, device_config)
            result = self.to_netjson_loop(interface, result, index)
            index += 1
        return result

    def to_netjson_loop(self, block, result, index):
        _type = block.get(".type")
        if _type == "globals":
            ula_prefix = block.get("ula_prefix")
            if ula_prefix:
                result = {"general": {"ula_prefix": ula_prefix}}
                _name = block.pop(".name")
                if _name != "globals":
                    result["general"]["globals_id"] = _name
        elif _type == "interface":
            if self.dsa:
                block = self.__netjson_dsa_interface(block)
            if (
                block
                and not self.__is_device_config(block)
                and not block.get("bridge_21", None)
            ):
                interface = self.__netjson_interface(block)
                if interface:
                    self.__netjson_dns(interface, result)
                    result.setdefault("interfaces", [])
                    result["interfaces"].append(interface)
        return result

    def __netjson_interface(self, interface):
        del interface[".type"]
        interface["network"] = interface.pop(".name")
        interface["device_name"] = interface.get("name")
        interface["name"] = interface.pop("ifname", interface["network"])
        interface["type"] = self.__netjson_type(interface)
        interface = self.__netjson_addresses(interface)
        if "auto" in interface:
            interface["autostart"] = interface.pop("auto") == "1"
        if "enabled" in interface:
            interface["disabled"] = interface.pop("enabled") == "0"
        if "mtu" in interface:
            interface["mtu"] = int(interface["mtu"])
        if "vid" in interface:
            interface["vid"] = int(interface["vid"])
        if "macaddr" in interface:
            interface["mac"] = interface.pop("macaddr")
        if interface["network"] == self._get_uci_name(interface["name"]):
            del interface["network"]
        # specific transformation
        method = getattr(self, f'_netjson_{interface.get("proto")}', None)
        if method:
            interface = method(interface)
        return interface

    def __get_device_config_for_interface(self, interface):
        device = interface.get("device", "")
        name = interface.get("name")
        device_config = self._device_config.get(device, self._device_config.get(name))
        if not device_config and "." in device:
            cleaned_device, _, _ = device.rpartition(".")
            device_config = self._device_config.get(cleaned_device)
        if not device_config:
            return device_config
        # ifname has been renamed to device in OpenWrt 21.02
        interface["ifname"] = interface.pop("device")
        return device_config

    def __add_options_from_device_config(self, interface, device_config):
        if device_config.get("bridge_21", None) and interface.get(
            "ifname"
        ) != device_config.get("name"):
            interface[".name"] = self._get_uci_name(interface["ifname"])
            return interface

        if device_config.get("consumed", False):
            return interface

        if device_config.get("bridge_21", None):
            for option in device_config:
                if option == "bridge_21":
                    continue
                # ifname has been renamed to ports in OpenWrt 21.02 bridge
                if option == "ports":
                    interface["ifname"] = " ".join(device_config[option])
                else:
                    interface[option] = device_config[option]

        # Merging L2 options to interface
        for options in (
            self._bridge_interface_options["all"]
            + self._bridge_interface_options["stp"]
            + self._bridge_interface_options["igmp_snooping"]
        ):
            if options in device_config:
                interface[options] = device_config.get(options)
        if device_config.get("type", "").startswith("8021"):
            interface["ifname"] = "".join(device_config["name"].split(".")[:-1])
        device_config["consumed"] = True
        return interface

    def _handle_bridge_vlan_interface(self, interface, device_config):
        ifname = interface.get("ifname", "")
        if "." not in ifname:
            # no VLAN suffix, nothing to do
            return interface

        _, _, vlan_id = interface["ifname"].rpartition(".")
        for vlan in device_config.get("vlan_filtering", []):
            if vlan["vlan"] == int(vlan_id):
                if interface.get("proto") == "none" and interface.keys() == {
                    ".type",
                    ".name",
                    "ifname",
                    "proto",
                }:
                    # Return None to ignore this auto-generated interface.
                    return
                # Auto-generated interface is being overridden by user.
                # Override the ".name" to avoid setting "network" field
                # in NetJSON output.
                interface[".name"] = self._get_uci_name(interface["ifname"])
                break
        return interface

    def __netjson_dsa_interface(self, interface):
        # Device configs are now handled in the first pass and removed,
        # so we only process actual interface blocks here
        device_config = self.__get_device_config_for_interface(interface)
        if device_config:
            interface = self._handle_bridge_vlan_interface(interface, device_config)
            if not interface:
                return
            interface = self.__add_options_from_device_config(interface, device_config)
        # if device_config is empty but the interface references it
        elif "device" in interface and "ifname" not in interface:
            # .name may have '.' substituted with _,
            # which will yield unexpected results
            # for this reason we use the name stored
            # in the device property before removing it
            interface["ifname"] = interface.pop("device")
        return interface

    def __netjson_device(self, interface):
        name = interface.pop(".name")
        # Remove "device_" prefix if present
        if name.startswith("device_"):
            interface["network"] = name[7:]  # len("device_") = 7
        else:
            interface["network"] = name
        for option in [
            "txqueuelen",
            "neighreachabletime",
            "neighgcstaletime",
            "neighlocktime",
            "igmpversion",
            "mldversion",
            "mtu",
            "mtu6",
            "dadtransmits",
        ]:
            try:
                value = interface.pop(option)
                interface[option] = int(value)
            except KeyError:
                continue

        for option in [
            "promisc",
            "acceptlocal",
            "sendredirects",
            "multicast",
        ]:
            try:
                value = interface.pop(option)
                assert value is not None
                interface[option] = value == "1"
            except KeyError:
                continue
        name = interface.get("name")
        try:
            self._device_config[name].update(interface)
        except KeyError:
            self._device_config[name] = interface

    def __netjson_vlan(self, vlan, device_config):
        # Clean up VLAN filtering option from the native config
        if device_config.get("vlan_filtering") == "1":
            device_config.pop("vlan_filtering")
        netjson_vlan = {"vlan": int(vlan["vlan"]), "ports": []}
        for port in vlan.get("ports", []):
            port_config = port.split(":")
            port = {
                "ifname": port_config[0],
                "tagging": "u",
                "primary_vid": False,
            }
            if len(port_config) > 1:
                port["tagging"] = port_config[1][0]
                if len(port_config[1]) > 1:
                    port["primary_vid"] = True
            netjson_vlan["ports"].append(port)
        try:
            device_config["vlan_filtering"].append(netjson_vlan)
        except KeyError:
            device_config["vlan_filtering"] = [netjson_vlan]
        return

    def __netjson_type(self, interface):
        device_name = interface.pop("device_name", None)
        if "type" in interface:
            if interface["type"] == "bridge":
                interface["bridge_members"] = interface["name"].split()
                interface["name"] = device_name or interface["network"]
                if not interface["name"].startswith("br-"):
                    interface["name"] = "br-{0}".format(interface["name"])
                # cleanup automatically generated "br_" network prefix
                interface["name"] = interface["name"].replace("br_", "")
                self.__netjson_bridge_typecast(interface)
                if interface.pop("bridge_empty", None) == "1":
                    interface["bridge_members"] = []
                return "bridge"
            if interface["type"].startswith("802"):
                return interface["type"]
        if interface["name"] in ["lo", "lo0", "loopback"]:
            return "loopback"
        return "ethernet"

    def __netjson_bridge_typecast(self, interface):
        for option in [
            "stp",
            "igmp_snooping",
            "multicast_querier",
        ]:
            if option in interface:
                interface[option] = interface[option] == "1"
        for option in [
            "forward_delay",
            "hello_time",
            "max_age",
            "priority",
            "query_interval",
            "query_response_interval",
            "last_member_interval",
            "hash_max",
            "robustness",
        ]:
            if option in interface:
                try:
                    interface[option] = int(interface[option])
                except ValueError:
                    del interface[option]

    def __netjson_addresses(self, interface):
        proto = interface.get("proto", "none")
        address_protos = ["static", "dhcp", "dhcpv6", "none"]
        if "proto" in interface and proto in address_protos:
            del interface["proto"]
        if "ipaddr" not in interface and "ip6addr" not in interface and proto == "none":
            return interface
        if proto not in address_protos:
            interface["type"] = "other"
        return self._add_netjson_addresses(interface, proto)

    def _add_netjson_addresses(self, interface, proto):
        addresses = []
        ipv4 = interface.pop("ipaddr", [])
        ipv6 = interface.pop("ip6addr", [])
        if not isinstance(ipv4, list):
            netmask = interface.pop("netmask", 32)
            parsed_ip = self.__netjson_parse_ip(ipv4, netmask)
            ipv4 = [parsed_ip] if parsed_ip else []
        if not isinstance(ipv6, list):
            netmask = interface.pop("netmask", 128)
            parsed_ip = self.__netjson_parse_ip(ipv6, netmask)
            ipv6 = [parsed_ip] if parsed_ip else []
        if proto.startswith("dhcp"):
            family = "ipv4" if proto == "dhcp" else "ipv6"
            addresses.append({"proto": "dhcp", "family": family})
        for address in ipv4 + ipv6:
            address = self.__netjson_parse_ip(address)
            if not address:
                continue
            addresses.append(self.__netjson_address(address, interface))
        if addresses:
            interface["addresses"] = addresses
        return interface

    def _netjson_dialup(self, interface):
        interface["type"] = "dialup"
        return interface

    _modem_manager_schema = schema["definitions"]["modemmanager_interface"]["allOf"][0]

    def _netjson_modem_manager(self, interface):
        del interface["proto"]
        interface["type"] = "modem-manager"
        interface["pin"] = interface.pop("pincode", None)
        return self.type_cast(interface, schema=self._modem_manager_schema)

    _netjson_modemmanager = _netjson_modem_manager

    _wireguard_schema = schema["definitions"]["wireguard_interface"]["allOf"][0]

    def _netjson_wireguard(self, interface):
        interface["type"] = interface.pop("proto", None)
        interface["port"] = interface.pop("listen_port", None)
        addresses = []
        for address in interface["addresses"]:
            cidr = ip_interface(address)
            addresses.append(
                {
                    "address": str(cidr.ip),
                    "mask": cidr.network.prefixlen,
                    "proto": "static",
                    "family": f"ipv{cidr.ip.version}",
                }
            )
        interface["addresses"] = addresses
        return self.type_cast(interface, schema=self._wireguard_schema)

    _vxlan_schema = schema["definitions"]["vxlan_interface"]["allOf"][0]

    def _netjson_vxlan(self, interface):
        interface["type"] = interface.pop("proto", None)
        interface["vtep"] = interface.pop("peeraddr", None)
        interface["vni"] = interface.pop("vid", None)
        interface["port"] = interface["port"]
        return self.type_cast(interface, schema=self._vxlan_schema)

    def __netjson_address(self, address, interface):
        ip = ip_interface(address)
        family = "ipv{0}".format(ip.version)
        netjson = OrderedDict(
            (
                ("address", str(ip.ip)),
                ("mask", ip.network.prefixlen),
                ("proto", "static"),
                ("family", family),
            )
        )
        uci_gateway_key = "gateway" if family == "ipv4" else "ip6gw"
        gateway = interface.get(uci_gateway_key, None)
        if gateway and ip_address(gateway) in ip.network:
            netjson["gateway"] = gateway
            del interface[uci_gateway_key]
        return netjson

    def __netjson_parse_ip(self, ip, netmask=32):
        if "/" in ip:
            parts = ip.split("/")
            ip = parts[0]
            netmask = parts[1] or netmask
        if ip and netmask:
            return "{0}/{1}".format(ip, netmask)
        else:
            return None

    def __netjson_dns(self, interface, result):
        key_mapping = {"dns": "dns_servers", "dns_search": "dns_search"}
        for uci_key, netjson_key in key_mapping.items():
            if uci_key not in interface:
                continue
            items = interface.pop(uci_key)
            if isinstance(items, str):
                items = items.split()
            result.setdefault(netjson_key, [])
            result[netjson_key] += items


for proto in [
    "3g",
    "6in4",
    "aiccu",
    "l2tp",
    "ncm",
    "ppp",
    "pppoa",
    "pppoe",
    "pptp",
    "qmi",
    "wwan",
]:
    setattr(Interfaces, f"_netjson_{proto}", Interfaces._netjson_dialup)
