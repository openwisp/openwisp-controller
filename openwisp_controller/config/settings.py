import logging

from django.conf import settings
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def get_settings_value(option, default):
    if option == 'CONFIG_BACKEND_FIELD_SHOWN' and hasattr(
        settings, 'OPENWISP_CONTROLLER_BACKEND_DEVICE_LIST'
    ):
        logger.warn(
            'OPENWISP_CONTROLLER_BACKEND_DEVICE_LIST is deprecated and will be '
            'removed in the future, please use '
            'OPENWISP_CONTROLLER_CONFIG_BACKEND_FIELD_SHOWN instead.'
        )
        return getattr(settings, 'OPENWISP_CONTROLLER_BACKEND_DEVICE_LIST', default)
    if hasattr(settings, f'NETJSONCONFIG_{option}'):
        logger.warn(
            f'NETJSONCONFIG_{option} setting is deprecated. It will be removed '
            f'in the future, please use OPENWISP_CONTROLLER_{option} instead.'
        )
        return getattr(settings, f'NETJSONCONFIG_{option}')
    return getattr(settings, f'OPENWISP_CONTROLLER_{option}', default)


BACKENDS = get_settings_value(
    'BACKENDS',
    (
        ('netjsonconfig.OpenWrt', 'OpenWRT'),
        ('netjsonconfig.OpenWisp', 'OpenWISP Firmware 1.x'),
    ),
)

VPN_BACKENDS = get_settings_value(
    'VPN_BACKENDS',
    (
        ('openwisp_controller.vpn_backends.OpenVpn', 'OpenVPN'),
        ('openwisp_controller.vpn_backends.Wireguard', 'WireGuard'),
        ('openwisp_controller.vpn_backends.VxlanWireguard', 'VXLAN over WireGuard'),
    ),
)
DEFAULT_BACKEND = get_settings_value('DEFAULT_BACKEND', BACKENDS[0][0])
DEFAULT_VPN_BACKEND = get_settings_value('DEFAULT_VPN_BACKEND', VPN_BACKENDS[0][0])
REGISTRATION_ENABLED = get_settings_value('REGISTRATION_ENABLED', True)
CONSISTENT_REGISTRATION = get_settings_value('CONSISTENT_REGISTRATION', True)
REGISTRATION_SELF_CREATION = get_settings_value('REGISTRATION_SELF_CREATION', True)

CONTEXT = get_settings_value('CONTEXT', {})
assert isinstance(CONTEXT, dict), 'OPENWISP_CONTROLLER_CONTEXT must be a dictionary'
DEFAULT_AUTO_CERT = get_settings_value('DEFAULT_AUTO_CERT', True)
CERT_PATH = get_settings_value('CERT_PATH', '/etc/x509')
COMMON_NAME_FORMAT = get_settings_value('COMMON_NAME_FORMAT', '{mac_address}-{name}')
MANAGEMENT_IP_DEVICE_LIST = get_settings_value('MANAGEMENT_IP_DEVICE_LIST', True)
CONFIG_BACKEND_FIELD_SHOWN = get_settings_value('CONFIG_BACKEND_FIELD_SHOWN', True)

HARDWARE_ID_ENABLED = get_settings_value('HARDWARE_ID_ENABLED', False)
HARDWARE_ID_OPTIONS = {
    'blank': not HARDWARE_ID_ENABLED,
    'null': True,
    'max_length': 32,
    'unique': False,
    'verbose_name': _('Serial number'),
    'help_text': _('Serial number of this device'),
}
HARDWARE_ID_OPTIONS.update(get_settings_value('HARDWARE_ID_OPTIONS', {}))
HARDWARE_ID_AS_NAME = get_settings_value('HARDWARE_ID_AS_NAME', True)
DEVICE_VERBOSE_NAME = get_settings_value(
    'DEVICE_VERBOSE_NAME', (_('Device'), _('Devices'))
)
DEVICE_NAME_UNIQUE = get_settings_value('DEVICE_NAME_UNIQUE', True)
DEVICE_GROUP_SCHEMA = get_settings_value(
    'DEVICE_GROUP_SCHEMA', {'type': 'object', 'properties': {}}
)
SHARED_MANAGEMENT_IP_ADDRESS_SPACE = get_settings_value(
    'SHARED_MANAGEMENT_IP_ADDRESS_SPACE', True
)
DSA_OS_MAPPING = get_settings_value('DSA_OS_MAPPING', {})
DSA_DEFAULT_FALLBACK = get_settings_value('DSA_DEFAULT_FALLBACK', True)
