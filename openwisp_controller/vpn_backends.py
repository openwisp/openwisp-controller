from copy import deepcopy

from netjsonconfig import OpenVpn as BaseOpenVpn
from netjsonconfig import VxlanWireguard as BaseVxlanWireguard
from netjsonconfig import Wireguard as BaseWireguard
from netjsonconfig import ZeroTier as BaseZeroTier
from netjsonconfig.backends.vxlan.schema import base_vxlan_properties

# adapt OpenVPN schema in order to limit it to 1 item only
limited_schema = deepcopy(BaseOpenVpn.schema)
limited_schema['properties']['openvpn'].update(
    {'additionalItems': False, 'minItems': 1, 'maxItems': 1}
)
# server mode only
limited_schema['properties']['openvpn']['items'].update(
    {
        'oneOf': [
            {'$ref': '#/definitions/server_bridged'},
            {'$ref': '#/definitions/server_routed'},
            {'$ref': '#/definitions/server_manual'},
        ]
    }
)
limited_schema['required'] = limited_schema.get('required', [])
limited_schema['required'].append('openvpn')

# default values for ca, cert and key
limited_schema['definitions']['tunnel']['properties']['ca']['default'] = 'ca.pem'
limited_schema['definitions']['tunnel']['properties']['cert']['default'] = 'cert.pem'
limited_schema['definitions']['tunnel']['properties']['key']['default'] = 'key.pem'
limited_schema['definitions']['server']['properties']['dh']['default'] = 'dh.pem'
limited_schema['properties']['files']['default'] = [
    {'path': 'ca.pem', 'mode': '0644', 'contents': '{{ ca }}'},
    {'path': 'cert.pem', 'mode': '0644', 'contents': '{{ cert }}'},
    {'path': 'key.pem', 'mode': '0644', 'contents': '{{ key }}'},
    {'path': 'dh.pem', 'mode': '0644', 'contents': '{{ dh }}'},
]


class OpenVpn(BaseOpenVpn):
    """
    modified OpenVpn backend
    its schema is adapted to be used as a VPN Server backend:
        * shows server only
        * allows only 1 vpn
        * adds default values for ca, cert, key and dh
    """

    schema = limited_schema


limited_wireguard_schema = deepcopy(BaseWireguard.schema)
wireguard_properties = limited_wireguard_schema['properties']['wireguard']
wireguard_properties.update({'maxItems': 1, 'minItems': 1})
# private key is handled automatically without the need of user input
del wireguard_properties['items']['properties']['private_key']
wireguard_properties['items']['required'].remove('private_key')


class Wireguard(BaseWireguard):
    """
    WireGuard
    """

    schema = limited_wireguard_schema


limited_vxlan_wireguard_schema = deepcopy(limited_wireguard_schema)
limited_vxlan_properties = deepcopy(base_vxlan_properties)
limited_vxlan_properties['vxlan'].update({'maxItems': 1, 'minItems': 1})
limited_vxlan_wireguard_schema['properties'].update(limited_vxlan_properties)


class VxlanWireguard(BaseVxlanWireguard):
    """
    VXLAN over WireGuard
    """

    schema = limited_vxlan_wireguard_schema


limited_zerotier_schema = deepcopy(BaseZeroTier.schema)
zerotier_server_properties = limited_zerotier_schema['definitions']['zerotier_server'][
    'properties'
]
# these properties handled automatically without the need of user input
del zerotier_server_properties['name']
del zerotier_server_properties['id']
del zerotier_server_properties['nwid']
del zerotier_server_properties['objtype']
del zerotier_server_properties['routes']
del zerotier_server_properties['revision']
del zerotier_server_properties['creationTime']
del zerotier_server_properties['ipAssignmentPools']
limited_zerotier_schema['definitions']['zerotier_server']['required'].remove('name')

zerotier_properties = limited_zerotier_schema['properties']['zerotier']
zerotier_properties.update({'additionalItems': False, 'maxItems': 1, 'minItems': 1})


class ZeroTier(BaseZeroTier):
    """
    ZeroTier
    """

    schema = limited_zerotier_schema
