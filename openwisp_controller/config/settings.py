import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def get_setting(option, default):
    return getattr(settings, f"OPENWISP_CONTROLLER_{option}", default)


BACKENDS = get_setting(
    "BACKENDS",
    (
        ("netjsonconfig.OpenWrt", "OpenWRT"),
        ("netjsonconfig.OpenWisp", "OpenWISP Firmware 1.x"),
    ),
)

VPN_BACKENDS = get_setting(
    "VPN_BACKENDS",
    (
        ("openwisp_controller.vpn_backends.OpenVpn", "OpenVPN"),
        ("openwisp_controller.vpn_backends.Wireguard", "WireGuard"),
        ("openwisp_controller.vpn_backends.VxlanWireguard", "VXLAN over WireGuard"),
        ("openwisp_controller.vpn_backends.ZeroTier", "ZeroTier"),
    ),
)
DEFAULT_BACKEND = get_setting("DEFAULT_BACKEND", BACKENDS[0][0])
DEFAULT_VPN_BACKEND = get_setting("DEFAULT_VPN_BACKEND", VPN_BACKENDS[0][0])
REGISTRATION_ENABLED = get_setting("REGISTRATION_ENABLED", True)
CONSISTENT_REGISTRATION = get_setting("CONSISTENT_REGISTRATION", True)
REGISTRATION_SELF_CREATION = get_setting("REGISTRATION_SELF_CREATION", True)

CONTEXT = get_setting("CONTEXT", {})
assert isinstance(CONTEXT, dict), "OPENWISP_CONTROLLER_CONTEXT must be a dictionary"
DEFAULT_AUTO_CERT = get_setting("DEFAULT_AUTO_CERT", True)
CERT_PATH = get_setting("CERT_PATH", "/etc/x509")
COMMON_NAME_FORMAT = get_setting("COMMON_NAME_FORMAT", "{mac_address}-{name}")
MANAGEMENT_IP_DEVICE_LIST = get_setting("MANAGEMENT_IP_DEVICE_LIST", True)
CONFIG_BACKEND_FIELD_SHOWN = get_setting("CONFIG_BACKEND_FIELD_SHOWN", True)

HARDWARE_ID_ENABLED = get_setting("HARDWARE_ID_ENABLED", False)
HARDWARE_ID_OPTIONS = {
    "blank": not HARDWARE_ID_ENABLED,
    "null": True,
    "max_length": 32,
    "unique": False,
    "verbose_name": _("Serial number"),
    "help_text": _("Serial number of this device"),
}
HARDWARE_ID_OPTIONS.update(get_setting("HARDWARE_ID_OPTIONS", {}))
HARDWARE_ID_AS_NAME = get_setting("HARDWARE_ID_AS_NAME", True)
DEVICE_VERBOSE_NAME = get_setting("DEVICE_VERBOSE_NAME", (_("Device"), _("Devices")))
DEVICE_NAME_UNIQUE = get_setting("DEVICE_NAME_UNIQUE", True)
DEVICE_GROUP_SCHEMA = get_setting(
    "DEVICE_GROUP_SCHEMA", {"type": "object", "properties": {}}
)
SHARED_MANAGEMENT_IP_ADDRESS_SPACE = get_setting(
    "SHARED_MANAGEMENT_IP_ADDRESS_SPACE", True
)
DSA_OS_MAPPING = get_setting("DSA_OS_MAPPING", {})
DSA_DEFAULT_FALLBACK = get_setting("DSA_DEFAULT_FALLBACK", True)
GROUP_PIE_CHART = get_setting("GROUP_PIE_CHART", False)
API_TASK_RETRY_OPTIONS = get_setting(
    "API_TASK_RETRY_OPTIONS",
    dict(max_retries=5, retry_backoff=True, retry_backoff_max=600, retry_jitter=True),
)
WHOIS_GEOIP_ACCOUNT = get_setting("WHOIS_GEOIP_ACCOUNT", None)
WHOIS_GEOIP_KEY = get_setting("WHOIS_GEOIP_KEY", None)
WHOIS_ENABLED = get_setting("WHOIS_ENABLED", False)
WHOIS_CONFIGURED = WHOIS_GEOIP_ACCOUNT and WHOIS_GEOIP_KEY
if WHOIS_ENABLED and not WHOIS_CONFIGURED:
    raise ImproperlyConfigured(
        "WHOIS_GEOIP_ACCOUNT and WHOIS_GEOIP_KEY must be set "
        + "when WHOIS_ENABLED is True."
    )
