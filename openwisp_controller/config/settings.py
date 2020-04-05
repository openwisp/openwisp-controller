from django.conf import settings
from django.utils.translation import ugettext_lazy as _

BACKENDS = getattr(
    settings,
    'NETJSONCONFIG_BACKENDS',
    (
        ('netjsonconfig.OpenWrt', 'OpenWRT'),
        ('netjsonconfig.OpenWisp', 'OpenWISP Firmware 1.x'),
    ),
)
VPN_BACKENDS = getattr(
    settings,
    'NETJSONCONFIG_VPN_BACKENDS',
    (('openwisp_controller.vpn_backends.OpenVpn', 'OpenVPN'),),
)
DEFAULT_BACKEND = getattr(settings, 'NETJSONCONFIG_DEFAULT_BACKEND', BACKENDS[0][0])
DEFAULT_VPN_BACKEND = getattr(
    settings, 'NETJSONCONFIG_DEFAULT_VPN_BACKEND', VPN_BACKENDS[0][0]
)
REGISTRATION_ENABLED = getattr(settings, 'NETJSONCONFIG_REGISTRATION_ENABLED', True)
CONSISTENT_REGISTRATION = getattr(
    settings, 'NETJSONCONFIG_CONSISTENT_REGISTRATION', True
)
REGISTRATION_SELF_CREATION = getattr(
    settings, 'NETJSONCONFIG_REGISTRATION_SELF_CREATION', True
)
SHARED_SECRET = getattr(settings, 'NETJSONCONFIG_SHARED_SECRET', '')
CONTEXT = getattr(settings, 'NETJSONCONFIG_CONTEXT', {})
assert isinstance(CONTEXT, dict), 'NETJSONCONFIG_CONTEXT must be a dictionary'
DEFAULT_AUTO_CERT = getattr(settings, 'NETJSONCONFIG_DEFAULT_AUTO_CERT', True)
CERT_PATH = getattr(settings, 'NETJSONCONFIG_CERT_PATH', '/etc/x509')
COMMON_NAME_FORMAT = getattr(
    settings, 'NETJSONCONFIG_COMMON_NAME_FORMAT', '{mac_address}-{name}'
)
MANAGEMENT_IP_DEVICE_LIST = getattr(
    settings, 'NETJSONCONFIG_MANAGEMENT_IP_DEVICE_LIST', True
)
BACKEND_DEVICE_LIST = getattr(settings, 'NETJSONCONFIG_BACKEND_DEVICE_LIST', True)

HARDWARE_ID_ENABLED = getattr(settings, 'NETJSONCONFIG_HARDWARE_ID_ENABLED', False)
HARDWARE_ID_OPTIONS = {
    'blank': not HARDWARE_ID_ENABLED,
    'null': True,
    'max_length': 32,
    'unique': True,
    'verbose_name': _('Serial number'),
    'help_text': _('Serial number of this device'),
}
HARDWARE_ID_OPTIONS.update(getattr(settings, 'NETJSONCONFIG_HARDWARE_ID_OPTIONS', {}))
HARDWARE_ID_AS_NAME = getattr(settings, 'NETJSONCONFIG_HARDWARE_ID_AS_NAME', True)
