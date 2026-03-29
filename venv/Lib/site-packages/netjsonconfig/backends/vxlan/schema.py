from copy import deepcopy

from ..wireguard.schema import schema as base_schema

base_vxlan_properties = {
    "vxlan": {
        "type": "array",
        "title": "VXLAN",
        "uniqueItems": True,
        "additionalItems": True,
        "propertyOrder": 13,
        "items": {
            "type": "object",
            "title": "VXLAN tunnel",
            "additionalProperties": True,
            "properties": {
                "name": {
                    "title": "interface name",
                    "description": "VXLAN interface name",
                    "type": "string",
                    "minLength": 2,
                    "maxLength": 15,
                    "pattern": "^[^\\s]*$",
                    "propertyOrder": 1,
                },
                "vni": {
                    "propertyOrder": 2,
                    "title": "VNI",
                    "oneOf": [
                        {
                            "title": "VNI (auto)",
                            "description": "Auto-generate (different for each tunnel)",
                            "type": "string",
                            "enum": [""],
                            "options": {"enum_titles": ["auto"]},
                            "readonly": True,
                        },
                        {
                            "title": "VNI (manual)",
                            "type": "integer",
                            "default": 1,
                            "minimum": 0,
                            "maximum": 16777216,
                        },
                    ],
                },
            },
        },
    }
}


schema = deepcopy(base_schema)
schema["properties"].update(base_vxlan_properties)
