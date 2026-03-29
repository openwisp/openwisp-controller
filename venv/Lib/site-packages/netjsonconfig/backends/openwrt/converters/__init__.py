from .default import Default
from .general import General
from .interfaces import Interfaces
from .led import Led
from .ntp import Ntp
from .openvpn import OpenVpn
from .radios import Radios
from .routes import Routes
from .rules import Rules
from .switch import Switch
from .wireguard_peers import WireguardPeers
from .wireless import Wireless
from .zerotier import ZeroTier

__all__ = [
    "Default",
    "Interfaces",
    "General",
    "Led",
    "Ntp",
    "OpenVpn",
    "Radios",
    "Routes",
    "Rules",
    "Switch",
    "WireguardPeers",
    "Wireless",
    "ZeroTier",
]
