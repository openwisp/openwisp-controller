from .backends.openvpn.openvpn import OpenVpn  # noqa
from .backends.openwisp.openwisp import OpenWisp  # noqa
from .backends.openwrt.openwrt import OpenWrt  # noqa
from .backends.vxlan.vxlan_wireguard import VxlanWireguard  # noqa
from .backends.wireguard.wireguard import Wireguard  # noqa
from .backends.zerotier.zerotier import ZeroTier  # noqa
from .version import VERSION, __version__, get_version  # noqa


def get_backends():
    default = {
        "openwrt": OpenWrt,
        "openwisp": OpenWisp,
        "openvpn": OpenVpn,
        "wireguard": Wireguard,
        "vxlan": VxlanWireguard,
        "zerotier": ZeroTier,
    }
    return default
