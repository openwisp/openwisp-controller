"""
ZeroTier specific JSON-Schema definition
"""

from copy import deepcopy

from ...schema import schema as default_schema

# The schema is taken from OpenAPI specification:
# https://docs.zerotier.com/service/v1/ (self-hosted controllers)
# https://docs.zerotier.com/openapi/centralv1.json (central controllers)
base_zerotier_schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "additionalProperties": True,
    "definitions": {
        "zerotier_server": {
            "type": "object",
            "title": "ZeroTier Network",
            "required": ["name"],
            "properties": {
                # Read-only properties
                "name": {
                    "type": "string",
                    # Since it is intended to be set by
                    # the VPN backend's name field, it is read-only
                    "readOnly": True,
                    "propertyOrder": 1,
                    "title": "Name",
                    "description": "Name of the network",
                },
                "id": {
                    "type": "string",
                    "maxLength": 16,
                    "readOnly": True,
                    "propertyOrder": 2,
                    "title": "Network ID",
                    "description": "Network ID",
                },
                "nwid": {
                    "type": "string",
                    "maxLength": 16,
                    "readOnly": True,
                    "propertyOrder": 3,
                    "title": "Network ID",
                    "description": "Network ID legacy field (same as 'id')",
                },
                "objtype": {
                    "type": "string",
                    "readOnly": True,
                    "propertyOrder": 4,
                    "title": "Object Type",
                    "default": "network",
                },
                "revision": {
                    "type": "integer",
                    "readOnly": True,
                    "propertyOrder": 5,
                    "title": "Revision Number",
                    "description": "The revision number of the network configuration",
                },
                "creationTime": {
                    "type": "number",
                    "readOnly": True,
                    "propertyOrder": 6,
                    "title": "Creation Time",
                    "description": "Time when the network was created",
                },
                # Configurable properties
                "client_options": {
                    "type": "object",
                    "title": "Client Options",
                    "propertyOrder": 14,
                    "properties": {
                        "allow_managed": {
                            "type": "boolean",
                            "title": "Allow Managed",
                            "default": True,
                            "format": "checkbox",
                            "description": (
                                "Allow ZeroTier to set IP Addresses and Routes (local/private ranges only)"
                            ),
                        },
                        "allow_global": {
                            "type": "boolean",
                            "title": "Allow Global",
                            "default": False,
                            "format": "checkbox",
                            "description": (
                                "Allow ZeroTier to set Global/Public/Not-Private range IPs and Routes"
                            ),
                        },
                        "allow_default": {
                            "type": "boolean",
                            "title": "Allow Default",
                            "format": "checkbox",
                            "description": (
                                "Allow ZeroTier to set the Default Route on the system"
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
                "capabilities": {
                    "type": "array",
                    "items": {"type": "object"},
                    "propertyOrder": 17,
                    "title": "Capabilities",
                    "description": "Array of network capabilities",
                },
                "dns": {
                    "type": "object",
                    "propertyOrder": 15,
                    "title": "DNS",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "propertyOrder": 1,
                            "title": "Search Domain",
                            "description": "The domain for DNS resolution",
                        },
                        "servers": {
                            "type": "array",
                            "propertyOrder": 2,
                            "title": "Server Address",
                            "items": {
                                "type": "string",
                                "title": "IP Address",
                                "description": "The DNS server IP addresses",
                            },
                        },
                    },
                },
                "enableBroadcast": {
                    "type": "boolean",
                    "default": True,
                    "format": "checkbox",
                    "propertyOrder": 8,
                    "title": "Enable Broadcast",
                    "description": "Enable broadcast packets on the network",
                },
                "ipAssignmentPools": {
                    "type": "array",
                    "propertyOrder": 14,
                    "title": "IPv4 Address Pools",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ipRangeStart": {
                                "type": "string",
                                "propertyOrder": 1,
                                "title": "IP Range Start",
                                "description": "The starting IP address of the pool range",
                            },
                            "ipRangeEnd": {
                                "type": "string",
                                "propertyOrder": 2,
                                "title": "IP Range End",
                                "description": "The ending IP address of the pool range",
                            },
                        },
                    },
                    "description": "Range of IP addresses for the auto assign pool",
                },
                "mtu": {
                    "type": "integer",
                    "default": 2800,
                    "propertyOrder": 10,
                    "title": "Maximum Transmission Unit",
                    "description": "MTU to set on the client virtual network adapter",
                },
                "multicastLimit": {
                    "type": "integer",
                    "default": 32,
                    "title": "Multicast Recipient Limit",
                    "propertyOrder": 9,
                    "description": (
                        "Maximum number of recipients per multicast or broadcast. "
                        "Warning - Setting this to 0 will disable IPv4 communication on your network!"
                    ),
                },
                "private": {
                    "type": "boolean",
                    "default": True,
                    "format": "checkbox",
                    "title": "Private",
                    "propertyOrder": 7,
                    "description": (
                        "Whether or not the network is private "
                        "If false, members will NOT need to be authorized to join"
                    ),
                },
                "remoteTraceLevel": {
                    "type": "integer",
                    "propertyOrder": 19,
                    "title": "Remote Trace Level",
                    "description": "The level of network tracing",
                },
                "remoteTraceTarget": {
                    "type": ["string", "null"],
                    "propertyOrder": 20,
                    "default": "",
                    "title": "Remote Trace Target",
                    "description": "The remote target ID for network tracing",
                },
                "routes": {
                    "type": "array",
                    "propertyOrder": 13,
                    "title": "Managed Routes",
                    "items": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "propertyOrder": 1,
                                "title": "Destination",
                                "description": "The target IP address range for the route",
                            },
                            "via": {
                                "type": "string",
                                "propertyOrder": 2,
                                "title": "Via",
                                "description": "The IP address of the next hop for the route",
                            },
                        },
                    },
                    "description": "Array of route objects",
                },
                "rules": {
                    "type": "array",
                    "items": {"type": "object"},
                    "propertyOrder": 16,
                    "title": "Flow Rules",
                    "description": "Array of network rule objects",
                    # This is the default rule set
                    # that allows IPv4 and IPv6 traffic
                    # It is based on the default
                    # network configuration from ZeroTier Central
                    # https://docs.zerotier.com/zerotier/rules
                    "default": [
                        {
                            "etherType": 2048,
                            "not": True,
                            "or": False,
                            "type": "MATCH_ETHERTYPE",
                        },
                        {
                            "etherType": 2054,
                            "not": True,
                            "or": False,
                            "type": "MATCH_ETHERTYPE",
                        },
                        {
                            "etherType": 34525,
                            "not": True,
                            "or": False,
                            "type": "MATCH_ETHERTYPE",
                        },
                        {"type": "ACTION_DROP"},
                        {"type": "ACTION_ACCEPT"},
                    ],
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "object"},
                    "propertyOrder": 18,
                    "title": "Tags",
                    "description": "Array of network tag objects",
                },
                "v4AssignMode": {
                    "type": "object",
                    "propertyOrder": 11,
                    "title": "IPv4 Auto-Assign",
                    "properties": {
                        "zt": {
                            "type": "boolean",
                            "format": "checkbox",
                            "title": "Auto-Assign from Range",
                            "description": "Whether ZeroTier should assign IPv4 addresses to members",
                        },
                    },
                },
                "v6AssignMode": {
                    "type": "object",
                    "propertyOrder": 12,
                    "title": "IPv6 Auto-Assign",
                    "properties": {
                        "6plane": {
                            "type": "boolean",
                            "format": "checkbox",
                            "title": "ZeroTier 6PLANE (/80 routable for each device)",
                            "description": (
                                "6PLANE assigns each device a single "
                                "IPv6 address from a fully routable /80 block. "
                                "It utilizes NDP emulation to route the entire /80 "
                                "to the device owner, enabling up to 2^48 IPs without "
                                "additional configuration. Ideal for Docker or VM hosts"
                            ),
                        },
                        "rfc4193": {
                            "type": "boolean",
                            "format": "checkbox",
                            "title": "ZeroTier RFC4193 (/128 for each device)",
                            "description": (
                                "RFC4193 assigns each device a "
                                "single IPv6 /128 address computed "
                                "from the network ID and device address, "
                                "and uses NDP emulation to make these addresses "
                                "instantly resolvable without multicast"
                            ),
                        },
                        "zt": {
                            "type": "boolean",
                            "format": "checkbox",
                            "title": "Auto-Assign from Range",
                            "description": "Whether ZeroTier should assign IPv6 addresses to members",
                        },
                    },
                },
            },
        },
    },
    "properties": {
        "zerotier": {
            "type": "array",
            "title": "ZeroTier",
            "uniqueItems": True,
            "additionalItems": True,
            "propertyOrder": 12,
            "items": {
                "type": "object",
                "title": "VPN",
                "additionalProperties": True,
                "allOf": [
                    {"$ref": "#/definitions/zerotier_server"},
                ],
            },
        }
    },
}

schema = deepcopy(base_zerotier_schema)
schema["required"] = ["zerotier"]
schema["properties"]["files"] = default_schema["properties"]["files"]
