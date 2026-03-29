"""
Wireguard specific JSON-Schema definition
"""

from copy import deepcopy

from ...schema import schema as default_schema

base_wireguard_schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "wireguard": {
            "type": "array",
            "title": "Wireguard",
            "uniqueItems": True,
            "additionalItems": True,
            "propertyOrder": 12,
            "items": {
                "type": "object",
                "title": "Wireguard tunnel",
                "additionalProperties": True,
                "required": ["name", "port", "private_key"],
                "properties": {
                    "name": {
                        "title": "interface name",
                        "description": "Wireguard interface name",
                        "type": "string",
                        "minLength": 2,
                        "maxLength": 15,
                        "pattern": "^[^\\s]*$",
                        "propertyOrder": 1,
                    },
                    "port": {
                        "title": "port",
                        "type": "integer",
                        "default": 51820,
                        "maximum": 65535,
                        "minimum": 1,
                        "propertyOrder": 2,
                    },
                    "private_key": {
                        "title": "private key",
                        "type": "string",
                        "maxLength": 44,
                        "pattern": "^[^\\s]*$",
                        "propertyOrder": 3,
                    },
                    "dns": {
                        "title": "DNS",
                        "type": "array",
                        "uniqueItems": True,
                        "propertyOrder": 4,
                        "items": {"title": "DNS", "type": "string"},
                        "propertyOrder": 4,
                    },
                    "mtu": {
                        "type": "integer",
                        "title": "MTU",
                        "minimum": 68,
                        "propertyOrder": 5,
                        "default": 1420,
                        "description": "Interface MTU, set to 1280 if using IPv6.",
                    },
                    "table": {
                        "title": "Table",
                        "type": "string",
                        "default": "auto",
                        "description": (
                            "Controls the routing table to which routes are added."
                            "There are two special values:"
                            " 'off' (disables the creation of routes altogether)"
                            " and 'auto' (adds routes to the default table and enables"
                            " special handling of default routes)."
                        ),
                        "propertyOrder": 6,
                    },
                    "pre_up": {
                        "title": "PreUp",
                        "type": "string",
                        "description": (
                            "Script snippet which will be executed before setting up the interface."
                            " The special string '%i' is expanded to INTERFACE."
                        ),
                        "format": "textarea",
                        "propertyOrder": 7,
                    },
                    "post_up": {
                        "title": "PostUp",
                        "type": "string",
                        "description": (
                            "Script snippet which will be executed after setting up the interface."
                            " The special string '%i' is expanded to INTERFACE."
                        ),
                        "format": "textarea",
                        "propertyOrder": 8,
                    },
                    "pre_down": {
                        "title": "PreDown",
                        "type": "string",
                        "description": (
                            "Script snippet which will be executed before tearing down the interface."
                            " The special string '%i' is expanded to INTERFACE."
                        ),
                        "format": "textarea",
                        "propertyOrder": 9,
                    },
                    "post_down": {
                        "title": "PostDown",
                        "type": "string",
                        "description": (
                            "Script snippet which will be executed after tearing down the interface."
                            " The special string '%i' is expanded to INTERFACE."
                        ),
                        "format": "textarea",
                        "propertyOrder": 10,
                    },
                    "save_config": {
                        "type": "boolean",
                        "title": "save config",
                        "default": False,
                        "format": "checkbox",
                        "description": (
                            "If set to `true', the configuration is saved from the current"
                            " state of the interface upon shutdown. "
                        ),
                        "propertyOrder": 11,
                    },
                    "peers": {
                        "type": "array",
                        "title": "Peers",
                        "uniqueItems": True,
                        "additionalItems": True,
                        "propertyOrder": 12,
                        "items": {
                            "type": "object",
                            "title": "Peer",
                            "required": ["public_key", "allowed_ips"],
                            "properties": {
                                "public_key": {
                                    "title": "public key",
                                    "type": "string",
                                    "maxLength": 44,
                                    "minLength": 1,
                                    "pattern": "^[^\\s]*$",
                                    "propertyOrder": 1,
                                },
                                "allowed_ips": {
                                    "title": "allowed IP addresses",
                                    "type": "string",
                                    "minLength": 1,
                                    "propertyOrder": 2,
                                },
                                "endpoint_host": {
                                    "title": "endpoint host",
                                    "type": "string",
                                    "propertyOrder": 3,
                                },
                                "endpoint_port": {
                                    "title": "endpoint port",
                                    "type": "integer",
                                    "description": (
                                        "Wireguard port. Will be ignored if "
                                        '"endpoint host" is left empty.'
                                    ),
                                    "default": 51820,
                                    "maximum": 65535,
                                    "minimum": 1,
                                    "propertyOrder": 4,
                                },
                                "preshared_key": {
                                    "title": "pre-shared key",
                                    "description": (
                                        "Optional shared secret, to provide an "
                                        "additional layer of symmetric-key cryptography "
                                        "for post-quantum resistance"
                                    ),
                                    "type": "string",
                                    "maxLength": 44,
                                    "pattern": "^[^\\s]*$",
                                    "propertyOrder": 5,
                                },
                            },
                        },
                    },
                },
            },
        }
    },
}

schema = deepcopy(base_wireguard_schema)
schema["required"] = ["wireguard"]
schema["properties"]["files"] = default_schema["properties"]["files"]
