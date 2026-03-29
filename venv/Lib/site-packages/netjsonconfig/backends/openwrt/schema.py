"""
OpenWrt specific JSON-Schema definition
"""

from ...schema import schema as default_schema
from ...utils import merge_config
from ..openvpn.schema import base_openvpn_schema
from ..wireguard.schema import base_wireguard_schema
from .timezones import timezones

QOS_MAPPING_PATTERN = r"^[0-9]\d*:[0-9]\d*$"

default_radio_driver = "mac80211"

wireguard = base_wireguard_schema["properties"]["wireguard"]["items"]["properties"]
wireguard_peers = wireguard["peers"]["items"]["properties"]
interface_settings = default_schema["definitions"]["interface_settings"]["properties"]

schema = merge_config(
    default_schema,
    {
        "definitions": {
            "base_interface_settings": {
                "properties": {
                    "network": {
                        "type": "string",
                        "description": "logical interface name in UCI (OpenWRT configuration format), "
                        "will be automatically generated if left blank",
                        "maxLength": 15,
                        "pattern": "^[a-zA-z0-9_\\.\\-]*$",
                        "propertyOrder": 7,
                    }
                }
            },
            "vlan_interface_settings": {
                "properties": {
                    "name": {"title": "Base device"},
                    "vid": {
                        "type": "integer",
                        "title": "VLAN ID",
                        "propertyOrder": 2,
                        "minimum": 0,
                    },
                    "ingress_qos_mapping": {
                        "type": "array",
                        "title": "Ingress QoS mapping",
                        "description": (
                            "Defines a mapping of VLAN header priority to the Linux"
                            " internal packet priority on incoming frames"
                        ),
                        "uniqueItems": True,
                        "additionalItems": False,
                        "items": {
                            "title": "Mapping",
                            "type": "string",
                            "pattern": QOS_MAPPING_PATTERN,
                        },
                        "propertyOrder": 18,
                    },
                    "egress_qos_mapping": {
                        "type": "array",
                        "title": "Egress QoS mapping",
                        "description": (
                            "Defines a mapping of Linux internal packet priority to VLAN header"
                            " priority but for outgoing frames"
                        ),
                        "uniqueItems": True,
                        "additionalItems": False,
                        "items": {
                            "title": "Mapping",
                            "type": "string",
                            "pattern": QOS_MAPPING_PATTERN,
                        },
                        "propertyOrder": 19,
                    },
                }
            },
            "wireless_interface": {
                "properties": {
                    "wireless": {
                        "properties": {
                            "network": {
                                "type": "array",
                                "title": "Attached Networks",
                                "description": 'override OpenWRT "network" config option of of wifi-iface '
                                "directive; will be automatically determined if left blank",
                                "uniqueItems": True,
                                "additionalItems": True,
                                "items": {
                                    "title": "network",
                                    "type": "string",
                                    "$ref": "#/definitions/base_interface_settings/properties/network",
                                },
                                "propertyOrder": 19,
                            }
                        }
                    }
                }
            },
            "ap_wireless_settings": {
                "allOf": [
                    {
                        "properties": {
                            "wmm": {
                                "type": "boolean",
                                "title": "WMM (802.11e)",
                                "description": "enables WMM (802.11e) support; "
                                "required for 802.11n support",
                                "default": True,
                                "format": "checkbox",
                                "propertyOrder": 8,
                            },
                            "isolate": {
                                "type": "boolean",
                                "title": "isolate clients",
                                "description": "isolate wireless clients from one another",
                                "default": False,
                                "format": "checkbox",
                                "propertyOrder": 9,
                            },
                            "ieee80211r": {
                                "type": "boolean",
                                "title": "roaming",
                                "description": "enables fast BSS transition (802.11r) support",
                                "default": False,
                                "format": "checkbox",
                                "propertyOrder": 9,
                            },
                            "reassociation_deadline": {
                                "type": "integer",
                                "title": "reassociation deadline",
                                "description": (
                                    "reassociation deadline in time units "
                                    "(TUs / 1.024 ms, 1000-65535)"
                                ),
                                "default": 1000,
                                "minimum": 1000,
                                "maximum": 65535,
                                "propertyOrder": 9,
                            },
                            "ft_psk_generate_local": {
                                "type": "boolean",
                                "title": "FT PSK generate local",
                                "description": "whether to generate FT response locally for PSK networks",
                                "default": False,
                                "format": "checkbox",
                                "propertyOrder": 9,
                            },
                            "ft_over_ds": {
                                "type": "boolean",
                                "title": "FT-over-DS",
                                "description": "whether to enable FT-over-DS",
                                "default": True,
                                "format": "checkbox",
                                "propertyOrder": 9,
                            },
                            "rsn_preauth": {
                                "type": "boolean",
                                "title": "WPA2-EAP pre-authentication",
                                "description": "allow preauthentication for WPA2-EAP networks",
                                "default": False,
                                "format": "checkbox",
                                "propertyOrder": 9,
                            },
                            "macfilter": {
                                "type": "string",
                                "title": "MAC Filter",
                                "description": 'specifies the mac filter policy, "disable" to disable '
                                'the filter, "allow" to treat it as whitelist or '
                                '"deny" to treat it as blacklist',
                                "enum": ["disable", "allow", "deny"],
                                "default": "disable",
                                "propertyOrder": 15,
                            },
                            "maclist": {
                                "type": "array",
                                "title": "MAC List",
                                "description": "mac addresses that will be filtered according to the policy "
                                'specified in the "macfilter" option',
                                "propertyOrder": 16,
                                "items": {
                                    "type": "string",
                                    "title": "MAC address",
                                    "pattern": "^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$",
                                    "minLength": 17,
                                    "maxLength": 17,
                                },
                            },
                        }
                    }
                ]
            },
            "bridge_interface": {
                "allOf": [
                    {
                        "properties": {
                            "igmp_snooping": {
                                "type": "boolean",
                                "title": "IGMP snooping",
                                "description": 'sets the "multicast_snooping" kernel setting for a bridge',
                                "default": False,
                                "format": "checkbox",
                                "propertyOrder": 5,
                            },
                            "multicast_querier": {
                                "type": "boolean",
                                "title": "IGMP multicast querier",
                                "description": (
                                    "enables the bridge as a multicast querier"
                                ),
                                "default": False,
                                "format": "checkbox",
                                "propertyOrder": 5,
                            },
                            "query_interval": {
                                "type": "integer",
                                "title": "IGMP query interval",
                                "description": (
                                    "time interval in centiseconds between"
                                    " multicast general queries"
                                ),
                                "default": 12500,
                                "propertyOrder": 5,
                            },
                            "query_response_interval": {
                                "type": "integer",
                                "title": "IGMP query response interval",
                                "description": (
                                    "the max response time in centiseconds inserted into"
                                    " the periodic general queries"
                                ),
                                "default": 1000,
                                "propertyOrder": 5,
                            },
                            "last_member_interval": {
                                "type": "integer",
                                "title": "IGMP last member interval",
                                "description": (
                                    "the maximum response time in centiseconds inserted into"
                                    " group-specific queries sent in response to leave group messages."
                                ),
                                "default": 100,
                                "propertyOrder": 5,
                            },
                            "hash_max": {
                                "type": "integer",
                                "title": "IGMP hash max",
                                "description": "size of kernel multicast hash table",
                                "default": 512,
                                "propertyOrder": 5,
                            },
                            "robustness": {
                                "type": "integer",
                                "title": "IGMP Robustness",
                                "description": "sets Startup Query Count and Last Member Count",
                                "default": 2,
                                "propertyOrder": 5,
                            },
                            "forward_delay": {
                                "type": "integer",
                                "title": "STP forward delay",
                                "description": (
                                    "time in seconds to spend in listening"
                                    " and learning states"
                                ),
                                "default": 4,
                                "minimum": 2,
                                "maximum": 30,
                                "propertyOrder": 4,
                            },
                            "hello_time": {
                                "type": "integer",
                                "title": "STP hello time",
                                "description": "time interval in seconds for STP hello packets",
                                "default": 2,
                                "minimum": 1,
                                "maximum": 10,
                                "propertyOrder": 4,
                            },
                            "priority": {
                                "type": "integer",
                                "title": "STP priority",
                                "description": "STP bridge priority",
                                "default": 32767,
                                "minimum": 0,
                                "maximum": 65535,
                                "propertyOrder": 4,
                            },
                            "ageing_time": {
                                "type": "integer",
                                "title": "STP ageing time",
                                "description": (
                                    "expiration time in seconds for dynamic MAC"
                                    " entries in the filtering DB"
                                ),
                                "default": 300,
                                "minimum": 10,
                                "maximum": 1000000,
                                "propertyOrder": 4,
                            },
                            "max_age": {
                                "type": "integer",
                                "title": "STP max age",
                                "description": (
                                    "timeout in seconds until topology updates on link loss"
                                ),
                                "default": 20,
                                "minimum": 0,
                                "maximum": 40,
                                "propertyOrder": 4,
                            },
                            "vlan_filtering": {
                                "type": "array",
                                "title": "VLAN Filtering",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "vlan": {
                                            "title": "VLAN",
                                            "type": "integer",
                                            "minimum": 0,
                                        },
                                        "ports": {
                                            "title": "Ports",
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "required": ["ifname", "tagging"],
                                                "properties": {
                                                    "ifname": {
                                                        "type": "string",
                                                    },
                                                    "tagging": {
                                                        "type": "string",
                                                        "enum": ["t", "u"],
                                                        "options": {
                                                            "enum_titles": [
                                                                "Egress tagged",
                                                                "Egress untagged",
                                                            ]
                                                        },
                                                    },
                                                    "primary_vid": {
                                                        "type": "boolean",
                                                        "title": "Primary VID",
                                                        "format": "checkbox",
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        }
                    }
                ]
            },
            "vlan_8021q": {
                "title": "VLAN (802.1q)",
                "type": "object",
                "required": ["type", "vid"],
                "allOf": [
                    {
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["8021q"],
                                "default": "8021q",
                                "propertyOrder": 1,
                            },
                        }
                    },
                    {"$ref": "#/definitions/base_interface_settings"},
                    {"$ref": "#/definitions/interface_settings"},
                    {"$ref": "#/definitions/vlan_interface_settings"},
                ],
            },
            "vlan_8021ad": {
                "title": "VLAN (802.1ad)",
                "type": "object",
                "required": ["type", "vid"],
                "allOf": [
                    {
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["8021ad"],
                                "default": "8021ad",
                                "propertyOrder": 1,
                            },
                        }
                    },
                    {"$ref": "#/definitions/base_interface_settings"},
                    {"$ref": "#/definitions/interface_settings"},
                    {"$ref": "#/definitions/vlan_interface_settings"},
                ],
            },
            "dialup_interface": {
                "title": "Dialup interface",
                "required": ["proto", "username", "password"],
                "allOf": [
                    {
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["dialup"],
                                "default": "dialup",
                                "propertyOrder": 1,
                            },
                            "proto": {
                                "type": "string",
                                "title": "protocol",
                                "enum": [
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
                                ],
                                "default": "pppoe",
                                "propertyOrder": 1.1,
                            },
                            "username": {
                                "type": "string",
                                "description": "username for authentication in protocols like PPPoE",
                                "propertyOrder": 9,
                            },
                            "password": {
                                "type": "string",
                                "description": "password for authentication in protocols like PPPoE",
                                "propertyOrder": 10,
                            },
                        }
                    },
                    {"$ref": "#/definitions/base_interface_settings"},
                    {"$ref": "#/definitions/interface_settings"},
                ],
            },
            "modemmanager_interface": {
                "type": "object",
                "title": "Modem manager interface",
                "required": ["name", "device"],
                "allOf": [
                    {
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["modem-manager"],
                                "default": "dialup",
                                "propertyOrder": 1,
                            },
                            "apn": {
                                "type": "string",
                                "title": "APN",
                                "propertyOrder": 1.1,
                            },
                            "pin": {
                                "type": "string",
                                "title": "PIN code",
                                "propertyOrder": 1.2,
                            },
                            "device": {
                                "type": "string",
                                "description": "Leave blank to use the hardware default",
                                "propertyOrder": 1.3,
                            },
                            "username": {"type": "string", "propertyOrder": 1.4},
                            "password": {"type": "string", "propertyOrder": 1.5},
                            "metric": {
                                "type": "integer",
                                "default": 50,
                                "propertyOrder": 1.6,
                            },
                            "iptype": {
                                "type": "string",
                                "title": "IP type",
                                "default": "ipv4",
                                "enum": ["ipv4", "ipv6", "ipv4v6"],
                                "options": {
                                    "enum_titles": ["IPv4", "IPv6", "IPv4 and IPv6"]
                                },
                                "propertyOrder": 1.7,
                            },
                            "lowpower": {
                                "type": "boolean",
                                "title": "Low power mode",
                                "format": "checkbox",
                                "default": False,
                                "propertyOrder": 1.8,
                            },
                            "signalrate": {
                                "type": "integer",
                                "title": "Signal refresh rate",
                                "propertyOrder": 1.9,
                                "description": "singal refresh rate in seconds",
                            },
                            "force_link": {
                                "type": "boolean",
                                "title": "Force link",
                                "format": "checkbox",
                                "default": True,
                                "description": (
                                    "Set interface properties regardless of the link carrier"
                                    " (If set, carrier sense events do not invoke hotplug handlers)."
                                ),
                                "propertyOrder": 1.11,
                            },
                            "loglevel": {
                                "type": "string",
                                "title": "Log output level",
                                "default": "ERR",
                                "enum": ["ERR", "WARN", "INFO", "DEBUG"],
                                "options": {
                                    "enum_titles": [
                                        "Error",
                                        "Warning",
                                        "Info",
                                        "Debug",
                                    ]
                                },
                                "propertyOrder": 1.12,
                            },
                        },
                    },
                    {"$ref": "#/definitions/base_interface_settings"},
                ],
            },
            "wireguard_interface": {
                "type": "object",
                "title": "Wireguard interface",
                "required": ["private_key"],
                "additionalProperties": True,
                "allOf": [
                    {
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["wireguard"],
                                "default": "wireguard",
                                "propertyOrder": 1,
                            },
                            "private_key": wireguard["private_key"],
                            "port": wireguard["port"],
                            "mtu": {
                                "type": "integer",
                                "default": 1420,
                                "propertyOrder": 1.1,
                            },
                            "nohostroute": {
                                "type": "boolean",
                                "format": "checkbox",
                                "default": False,
                                "title": "no host route",
                                "description": (
                                    "Do not add routes to ensure the tunnel "
                                    "endpoints are routed via non-tunnel device"
                                ),
                                "propertyOrder": 3,
                            },
                            "fwmark": {
                                "type": "string",
                                "title": "firewall mark",
                                "description": (
                                    "Firewall mark to apply to tunnel endpoint packets, "
                                    "will be automatically determined if left blank"
                                ),
                                "propertyOrder": 3.1,
                            },
                            "ip6prefix": {
                                "title": "IPv6 prefixes",
                                "description": "IPv6 prefixes to delegate to other interfaces",
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "title": "IPv6 prefix",
                                    "uniqueItems": True,
                                },
                                "propertyOrder": 9,
                            },
                            # unfortunately some duplication with the base IP address
                            # definition is needed to achieve functional usability and
                            # consistency with the rest of the schema because the
                            # wireguard OpenWRT package uses a different configuration
                            # format for addresses
                            "addresses": {
                                "type": "array",
                                "title": "addresses",
                                "uniqueItems": True,
                                "propertyOrder": 20,
                                "items": {
                                    "required": ["proto", "family", "address", "mask"],
                                    "title": "address",
                                    "oneOf": [
                                        {
                                            "type": "object",
                                            "title": "ipv4",
                                            "properties": {
                                                "proto": {
                                                    "title": "protocol",
                                                    "type": "string",
                                                    "propertyOrder": 1,
                                                    "enum": ["static"],
                                                },
                                                "family": {
                                                    "title": "family",
                                                    "type": "string",
                                                    "propertyOrder": 2,
                                                    "enum": ["ipv4"],
                                                },
                                                "address": {
                                                    "type": "string",
                                                    "title": "ipv4 address",
                                                    "minLength": 7,
                                                    "propertyOrder": 3,
                                                },
                                                "mask": {
                                                    "type": "number",
                                                    "minimum": 8,
                                                    "maxmium": 32,
                                                    "default": 32,
                                                },
                                            },
                                        },
                                        {
                                            "type": "object",
                                            "title": "ipv6",
                                            "properties": {
                                                "proto": {
                                                    "title": "protocol",
                                                    "type": "string",
                                                    "propertyOrder": 1,
                                                    "enum": ["static"],
                                                },
                                                "family": {
                                                    "title": "family",
                                                    "type": "string",
                                                    "propertyOrder": 2,
                                                    "enum": ["ipv6"],
                                                },
                                                "address": {
                                                    "type": "string",
                                                    "title": "ipv6 address",
                                                    "minLength": 3,
                                                    "format": "ipv6",
                                                    "propertyOrder": 3,
                                                },
                                                "mask": {
                                                    "type": "number",
                                                    "minimum": 4,
                                                    "maxmium": 128,
                                                    "default": 128,
                                                },
                                            },
                                        },
                                    ],
                                },
                            },
                        }
                    },
                    {"$ref": "#/definitions/base_interface_settings"},
                ],
            },
            "vxlan_interface": {
                "title": "VXLAN interface",
                "required": ["vtep", "port", "vni", "tunlink"],
                "allOf": [
                    {
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["vxlan"],
                                "default": "vxlan",
                                "propertyOrder": 1,
                            },
                            "vtep": {
                                "type": "string",
                                "title": "VTEP",
                                "description": "VXLAN Tunnel End Point",
                                "propertyOrder": 1.1,
                            },
                            "port": {
                                "type": "integer",
                                "propertyOrder": 1.2,
                                "default": 4789,
                                "minimum": 1,
                                "maximum": 65535,
                            },
                            "vni": {
                                "type": ["integer", "string"],
                                "title": "VNI",
                                "description": "VXLAN Network Identifier",
                                "propertyOrder": 1.3,
                                "minimum": 1,
                                "maximum": 16777216,
                            },
                            "tunlink": {
                                "type": "string",
                                "title": "TUN link",
                                "description": "Interface to which the VXLAN tunnel will be bound",
                                "propertyOrder": 1.4,
                            },
                            "rxcsum": {
                                "type": "boolean",
                                "title": "RX checksum validation",
                                "description": "Use checksum validation in RX (receiving) direction",
                                "default": True,
                                "format": "checkbox",
                                "propertyOrder": 1.5,
                            },
                            "txcsum": {
                                "type": "boolean",
                                "title": "TX checksum validation",
                                "description": "Use checksum validation in TX (transmission) direction",
                                "default": True,
                                "format": "checkbox",
                                "propertyOrder": 1.6,
                            },
                            "mtu": {"type": "integer", "default": 1280},
                            "ttl": {
                                "type": "integer",
                                "title": "TTL",
                                "description": "TTL of the encapsulation packets",
                                "default": 64,
                                "propertyOrder": 3,
                            },
                            "mac": interface_settings["mac"],
                        }
                    },
                    {"$ref": "#/definitions/base_interface_settings"},
                ],
            },
            "base_radio_settings": {
                "properties": {
                    "driver": {
                        "type": "string",
                        "enum": ["mac80211", "atheros", "ath5k", "ath9k", "broadcom"],
                        "default": default_radio_driver,
                        "propertyOrder": 2,
                    }
                }
            },
            "radio_hwmode_11g": {
                "properties": {
                    "hwmode": {
                        "type": "string",
                        "title": "hardware mode",
                        "readOnly": True,
                        "propertyOrder": 8,
                        "default": "11g",
                        "enum": ["11g"],
                    },
                },
            },
            "radio_hwmode_11a": {
                "properties": {
                    "hwmode": {
                        "type": "string",
                        "title": "hardware mode",
                        "readOnly": True,
                        "propertyOrder": 8,
                        "default": "11a",
                        "enum": ["11a"],
                    }
                },
            },
            "radio_2g_band": {
                "properties": {
                    "band": {
                        "type": "string",
                        "title": "band",
                        "readOnly": True,
                        "propertyOrder": 9,
                        "default": "2g",
                        "enum": ["2g"],
                    }
                },
            },
            "radio_5g_band": {
                "properties": {
                    "band": {
                        "type": "string",
                        "title": "band",
                        "readOnly": True,
                        "propertyOrder": 9,
                        "default": "5g",
                        "enum": ["5g"],
                    }
                },
            },
            "radio_6g_band": {
                "properties": {
                    "band": {
                        "type": "string",
                        "title": "band",
                        "readOnly": True,
                        "propertyOrder": 9,
                        "default": "6g",
                        "enum": ["6g"],
                    }
                },
            },
            "radio_60g_band": {
                "properties": {
                    "band": {
                        "type": "string",
                        "title": "band",
                        "readOnly": True,
                        "propertyOrder": 8,
                        "default": "60g",
                        "enum": ["60g"],
                    }
                },
            },
            "radio_80211gn_settings": {
                "allOf": [
                    {"$ref": "#/definitions/radio_hwmode_11g"},
                    {"$ref": "#/definitions/radio_2g_band"},
                ]
            },
            "radio_80211an_settings": {
                "allOf": [
                    {"$ref": "#/definitions/radio_hwmode_11a"},
                    {"$ref": "#/definitions/radio_5g_band"},
                ]
            },
            "radio_80211ac_5ghz_settings": {
                "allOf": [
                    {"$ref": "#/definitions/radio_hwmode_11a"},
                    {"$ref": "#/definitions/radio_5g_band"},
                ]
            },
            "radio_80211ax_2ghz_settings": {
                "allOf": [
                    {"$ref": "#/definitions/radio_hwmode_11g"},
                    {"$ref": "#/definitions/radio_2g_band"},
                ]
            },
            "radio_80211ax_5ghz_settings": {
                "allOf": [
                    {"$ref": "#/definitions/radio_hwmode_11a"},
                    {"$ref": "#/definitions/radio_5g_band"},
                ]
            },
            "radio_80211ax_6ghz_settings": {
                "allOf": [
                    {"$ref": "#/definitions/radio_6g_band"},
                ]
            },
            "radio_80211ad_60ghz_settings": {
                "allOf": [
                    {"$ref": "#/definitions/radio_60g_band"},
                ]
            },
            "encryption_wpa_enterprise_ap_base_settings": {
                "properties": {
                    "acct_secret": {
                        "title": "accounting shared secret",
                        "type": "string",
                        "propertyOrder": 9,
                    },
                    "acct_interval": {
                        "type": "integer",
                        "title": "accounting interval",
                        "default": 600,
                        "propertyOrder": 10,
                    },
                    "dae_client": {
                        "title": "DAE client",
                        "type": "string",
                        "description": (
                            "Dynamic Authorization Extension client."
                            ' This client can send "Disconnect-Request"'
                            ' or "CoA-Request" packets to forcibly disconnect a client'
                            " or change connection parameters."
                        ),
                        "propertyOrder": 11,
                    },
                    "dae_port": {
                        "type": "integer",
                        "title": "DAE port",
                        # "description": "port the Dynamic Authorization Extension server listens on.",
                        "default": 3799,
                        "propertyOrder": 12,
                    },
                    "dae_secret": {
                        "title": "DAE secret",
                        "type": "string",
                        "propertyOrder": 13,
                    },
                    "nasid": {
                        "title": "NAS ID",
                        "type": "string",
                        "description": "NAS ID for RADIUS authentication requests",
                        "propertyOrder": 13,
                    },
                }
            },
            "encryption_wpa_enterprise_sta_base_settings": {
                "properties": {
                    "ca_cert_usesystem": {
                        "title": "Use system certificates",
                        "type": "boolean",
                        "default": False,
                        "format": "checkbox",
                        "description": (
                            "Validate server certificate using built-in"
                            ' system CA bundle, requires the "ca-bundle" package'
                        ),
                        "propertyOrder": 7.9,
                    },
                    "subject_match": {
                        "title": "Certificate constraint (Subject)",
                        "type": "string",
                        "description": (
                            "Certificate constraint substring"
                            " - e.g. /CN=wifi.mycompany.com See `logread -f` during"
                            " handshake for actual values"
                        ),
                        "propertyOrder": 8.9,
                    },
                    "altsubject_match": {
                        "title": "Certificate constraint (SAN)",
                        "description": (
                            "Certificate constraint(s) via Subject Alternate"
                            " Name values (supported attributes: EMAIL, DNS, URI)"
                            " - e.g. DNS:wifi.mycompany.com"
                        ),
                        "type": "array",
                        "items": {"type": "string"},
                        "propertyOrder": 8.91,
                    },
                    "domain_match": {
                        "title": "Certificate constraint (Domain)",
                        "description": (
                            "Certificate constraint(s) against DNS SAN values"
                            " (if available) or Subject CN (exact match)"
                        ),
                        "type": "array",
                        "items": {"type": "string"},
                        "propertyOrder": 8.92,
                    },
                    "domain_suffix_match": {
                        "title": "Certificate constraint (Wildcard)",
                        "description": (
                            "Certificate constraint(s) against DNS SAN values "
                            "(if available) or Subject CN (suffix match)"
                        ),
                        "type": "array",
                        "items": {"type": "string"},
                        "propertyOrder": 8.93,
                    },
                }
            },
        },
        "properties": {
            "general": {
                "properties": {
                    "timezone": {"enum": list(timezones.keys()), "default": "UTC"}
                }
            },
            "interfaces": {
                "items": {
                    "oneOf": [
                        {"$ref": "#/definitions/dialup_interface"},
                        {"$ref": "#/definitions/modemmanager_interface"},
                        {"$ref": "#/definitions/vxlan_interface"},
                        {"$ref": "#/definitions/wireguard_interface"},
                        {"$ref": "#/definitions/vlan_8021q"},
                        {"$ref": "#/definitions/vlan_8021ad"},
                    ]
                }
            },
            "routes": {
                "items": {
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": [
                                "unicast",
                                "local",
                                "broadcast",
                                "multicast",
                                "unreachable",
                                "prohibit",
                                "blackhole",
                                "anycast",
                            ],
                            "default": "unicast",
                            "propertyOrder": 0,
                        },
                        "mtu": {
                            "type": "string",
                            "title": "MTU",
                            "propertyOrder": 6,
                            "pattern": "^[0-9]*$",
                        },
                        "table": {
                            "type": "string",
                            "propertyOrder": 7,
                            "pattern": "^[0-9]*$",
                        },
                        "onlink": {
                            "type": "boolean",
                            "default": False,
                            "format": "checkbox",
                            "propertyOrder": 8,
                        },
                    }
                }
            },
            "ip_rules": {
                "type": "array",
                "title": "Policy routing",
                "uniqueItems": True,
                "additionalItems": True,
                "propertyOrder": 7,
                "items": {
                    "type": "object",
                    "title": "IP rule",
                    "additionalProperties": True,
                    "properties": {
                        "in": {
                            "type": "string",
                            "title": "incoming interface",
                            "propertyOrder": 1,
                        },
                        "out": {
                            "type": "string",
                            "title": "outgoing interface",
                            "propertyOrder": 2,
                        },
                        "src": {
                            "type": "string",
                            "title": "source subnet",
                            "description": "(CIDR notation)",
                            "propertyOrder": 3,
                            "format": "cidr",
                        },
                        "dest": {
                            "type": "string",
                            "title": "destination subnet",
                            "description": "(CIDR notation)",
                            "propertyOrder": 4,
                            "format": "cidr",
                        },
                        "tos": {
                            "type": "integer",
                            "title": "TOS",
                            "description": "TOS value to match in IP headers",
                            "propertyOrder": 5,
                        },
                        "mark": {
                            "type": "string",
                            "description": "TOS value to match in IP headers",
                            "propertyOrder": 6,
                        },
                        "lookup": {
                            "type": "string",
                            "description": "routing table ID or symbolic link alias",
                            "propertyOrder": 7,
                        },
                        "action": {
                            "type": "string",
                            "enum": ["prohibit", "unreachable", "blackhole", "throw"],
                            "propertyOrder": 8,
                        },
                        "goto": {"type": "integer", "propertyOrder": 9},
                        "invert": {
                            "type": "boolean",
                            "default": False,
                            "format": "checkbox",
                            "propertyOrder": 10,
                        },
                    },
                },
            },
            "ntp": {
                "type": "object",
                "title": "NTP Settings",
                "additionalProperties": True,
                "propertyOrder": 8,
                "properties": {
                    "enabled": {
                        "type": "boolean",
                        "title": "enable NTP client",
                        "default": True,
                        "format": "checkbox",
                        "propertyOrder": 1,
                    },
                    "enable_server": {
                        "type": "boolean",
                        "title": "enable NTP server",
                        "default": False,
                        "format": "checkbox",
                        "propertyOrder": 2,
                    },
                    "server": {
                        "title": "NTP Servers",
                        "description": "NTP server candidates",
                        "type": "array",
                        "uniqueItems": True,
                        "additionalItems": True,
                        "propertyOrder": 3,
                        "items": {
                            "title": "NTP server",
                            "type": "string",
                            "format": "hostname",
                        },
                        "default": [
                            "0.openwrt.pool.ntp.org",
                            "1.openwrt.pool.ntp.org",
                            "2.openwrt.pool.ntp.org",
                            "3.openwrt.pool.ntp.org",
                        ],
                    },
                },
            },
            "switch": {
                "type": "array",
                "uniqueItems": True,
                "additionalItems": True,
                "title": "Programmable Switch",
                "propertyOrder": 9,
                "items": {
                    "title": "Switch",
                    "type": "object",
                    "additionalProperties": True,
                    "required": ["name", "reset", "enable_vlan", "vlan"],
                    "properties": {
                        "name": {"type": "string", "propertyOrder": 1},
                        "reset": {
                            "type": "boolean",
                            "default": True,
                            "format": "checkbox",
                            "propertyOrder": 2,
                        },
                        "enable_vlan": {
                            "type": "boolean",
                            "title": "enable vlan",
                            "default": True,
                            "format": "checkbox",
                            "propertyOrder": 3,
                        },
                        "vlan": {
                            "type": "array",
                            "title": "VLANs",
                            "uniqueItems": True,
                            "additionalItems": True,
                            "propertyOrder": 4,
                            "items": {
                                "type": "object",
                                "title": "VLAN",
                                "additionalProperties": True,
                                "required": ["device", "vlan", "ports"],
                                "properties": {
                                    "device": {"type": "string", "propertyOrder": 1},
                                    "vlan": {"type": "integer", "propertyOrder": 2},
                                    "ports": {"type": "string", "propertyOrder": 3},
                                },
                            },
                        },
                    },
                },
            },
            "led": {
                "type": "array",
                "title": "LEDs",
                "uniqueItems": True,
                "additionalItems": True,
                "propertyOrder": 10,
                "items": {
                    "type": "object",
                    "title": "LED",
                    "additionalProperties": True,
                    "required": ["name", "sysfs", "trigger"],
                    "properties": {
                        "name": {"type": "string", "propertyOrder": 1},
                        "default": {
                            "type": "boolean",
                            "format": "checkbox",
                            "propertyOrder": 2,
                        },
                        "dev": {"type": "string", "propertyOrder": 3},
                        "sysfs": {"type": "string", "propertyOrder": 4},
                        "trigger": {"type": "string", "propertyOrder": 5},
                        "delayoff": {"type": "integer", "propertyOrder": 6},
                        "delayon": {"type": "integer", "propertyOrder": 7},
                        "interval": {"type": "integer", "propertyOrder": 8},
                        "message": {"type": "string", "propertyOrder": 9},
                        "mode": {"type": "string", "propertyOrder": 10},
                    },
                },
            },
            "wireguard_peers": {
                "type": "array",
                "title": "Wireguard Peers",
                "uniqueItems": True,
                "propertyOrder": 13,
                "items": {
                    "type": "object",
                    "title": "Wireguard peer",
                    "additionalProperties": True,
                    "required": ["interface", "public_key", "allowed_ips"],
                    "properties": {
                        "interface": {
                            "type": "string",
                            "title": "interface",
                            "description": "name of the wireguard interface",
                            "minLength": 2,
                            "maxLength": 15,
                            "pattern": "^[^\\s]*$",
                            "propertyOrder": 0,
                        },
                        "public_key": wireguard_peers["public_key"],
                        "allowed_ips": {
                            "type": "array",
                            "title": "allowed IPs",
                            "propertyOrder": 2,
                            "uniqueItems": True,
                            "items": {
                                "type": "string",
                                "title": "IP/prefix",
                                "minLength": 1,
                            },
                        },
                        "endpoint_host": wireguard_peers["endpoint_host"],
                        "endpoint_port": wireguard_peers["endpoint_port"],
                        "preshared_key": wireguard_peers["preshared_key"],
                        "persistent_keepalive": {
                            "type": "integer",
                            "title": "keep alive",
                            "description": (
                                "Number of second between keepalive "
                                "messages, 0 means disabled"
                            ),
                            "default": 0,
                            "propertyOrder": 6,
                        },
                        "route_allowed_ips": {
                            "type": "boolean",
                            "format": "checkbox",
                            "title": "route allowed IPs",
                            "description": (
                                "Automatically create a route for "
                                "each Allowed IPs for this peer"
                            ),
                            "default": False,
                            "propertyOrder": 7,
                        },
                    },
                },
            },
            "zerotier": {
                "type": "array",
                "title": "ZeroTier Networks",
                "uniqueItems": True,
                "propertyOrder": 14,
                "items": {
                    "type": "object",
                    "title": "Network Member Configuration",
                    "additionalProperties": True,
                    "required": ["name", "networks"],
                    "properties": {
                        # ZeroTier customization (disabled) for OpenWRT
                        "disabled": {
                            "title": "disabled",
                            "description": "Disable this VPN without deleting its configuration",
                            "type": "boolean",
                            "default": False,
                            "format": "checkbox",
                            "propertyOrder": 1,
                        },
                        "name": {
                            "type": "string",
                            "propertyOrder": 2,
                            "default": "global",
                            "minLength": 1,
                            "description": "Name of the zerotier network member configuration",
                        },
                        "networks": {
                            "type": "array",
                            "title": "Networks",
                            "propertyOrder": 3,
                            "uniqueItems": True,
                            "additionalProperties": True,
                            "items": {
                                "type": "object",
                                "title": "Network Member",
                                "allOf": [{"required": ["id", "ifname"]}],
                                "properties": {
                                    "id": {
                                        "type": "string",
                                        "title": "Network ID",
                                        "maxLength": 16,
                                        "minLength": 16,
                                        "description": "Network ID to join",
                                    },
                                    "ifname": {
                                        "type": "string",
                                        "title": "Interface name",
                                        "minLength": 1,
                                        "maxLength": 10,
                                        "description": "Name of zerotier interface",
                                    },
                                    "allow_managed": {
                                        "type": "boolean",
                                        "title": "Allow Managed",
                                        "default": True,
                                        "format": "checkbox",
                                        "description": (
                                            "Allow ZeroTier to set IP Addresses"
                                            " and Routes (local/private ranges only)"
                                        ),
                                    },
                                    "allow_global": {
                                        "type": "boolean",
                                        "title": "Allow Global",
                                        "default": False,
                                        "format": "checkbox",
                                        "description": (
                                            "Allow ZeroTier to set Global/Public/Not-Private"
                                            " range IPs and Routes"
                                        ),
                                    },
                                    "allow_default": {
                                        "type": "boolean",
                                        "title": "Allow Default",
                                        "format": "checkbox",
                                        "description": (
                                            "Allow ZeroTier to set the Default Route on the"
                                            " system"
                                        ),
                                    },
                                    "allow_dns": {
                                        "type": "boolean",
                                        "title": "Allow DNS",
                                        "format": "checkbox",
                                        "description": "Allow ZeroTier to set DNS servers",
                                    },
                                },
                            },
                        },
                        "secret": {
                            "type": "string",
                            "propertyOrder": 4,
                            "default": "{{secret}}",
                            "description": (
                                "Identity secret of the zerotier client (network member), "
                                "You can leave it as the default and OpenWISP will automatically determine it"
                            ),
                        },
                        # Hidden properties
                        "config_path": {
                            "type": "string",
                            "propertyOrder": 5,
                            "options": {"hidden": True},
                            "default": "/etc/openwisp/zerotier",
                            "description": (
                                "Path to the persistent configuration "
                                "directory (for zerotier controller mode)"
                            ),
                        },
                        "copy_config_path": {
                            "type": "string",
                            "propertyOrder": 6,
                            "options": {"hidden": True},
                            "enum": ["0", "1"],
                            "default": "1",
                            "description": (
                                "Specifies whether to copy the configuration "
                                "file to RAM ('0' - No, '1' - Yes), this prevents "
                                "writing to flash in zerotier controller mode"
                            ),
                        },
                        "port": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 65535,
                            "default": 9993,
                            "propertyOrder": 7,
                            "description": "Port number of the zerotier service",
                        },
                        "local_conf_path": {
                            "type": "string",
                            "propertyOrder": 8,
                            "description": (
                                "Path of the local zerotier configuration "
                                "(only used for advanced configuration)"
                            ),
                        },
                    },
                },
            },
        },
    },
)

# add OpenVPN schema
schema = merge_config(schema, base_openvpn_schema)
# OpenVPN customizations for OpenWRT
schema = merge_config(
    schema,
    {
        "definitions": {
            "tunnel": {
                "properties": {
                    "disabled": {
                        "title": "disabled",
                        "description": "disable this VPN without deleting its configuration",
                        "type": "boolean",
                        "default": False,
                        "format": "checkbox",
                        "propertyOrder": 1,
                    }
                }
            }
        }
    },
)
