from django.conf import settings

DEFAULT_CONNECTORS = (('openwisp_controller.connection.connectors.ssh.Ssh', 'SSH'),)

CONNECTORS = getattr(settings, 'OPENWISP_CONNECTORS', DEFAULT_CONNECTORS)

DEFAULT_UPDATE_STRATEGIES = (
    ('openwisp_controller.connection.connectors.openwrt.ssh.OpenWrt', 'OpenWRT SSH'),
    (
        'openwisp_controller.connection.connectors.openwrt.ssh.OpenWisp1',
        'OpenWISP 1.x SSH',
    ),
)

UPDATE_STRATEGIES = getattr(
    settings, 'OPENWISP_UPDATE_STRATEGIES', DEFAULT_UPDATE_STRATEGIES
)

CONFIG_UPDATE_MAPPING = getattr(
    settings,
    'OPENWISP_CONFIG_UPDATE_MAPPING',
    {
        'netjsonconfig.OpenWrt': DEFAULT_UPDATE_STRATEGIES[0][0],
        'netjsonconfig.OpenWisp': DEFAULT_UPDATE_STRATEGIES[1][0],
    },
)

SSH_AUTH_TIMEOUT = getattr(settings, 'OPENWISP_SSH_AUTH_TIMEOUT', 2)
SSH_BANNER_TIMEOUT = getattr(settings, 'OPENWISP_SSH_BANNER_TIMEOUT', 60)
SSH_COMMAND_TIMEOUT = getattr(settings, 'OPENWISP_SSH_COMMAND_TIMEOUT', 30)
SSH_CONNECTION_TIMEOUT = getattr(settings, 'OPENWISP_SSH_CONNECTION_TIMEOUT', 5)

# this may get overridden by openwisp-monitoring
UPDATE_CONFIG_MODEL = getattr(settings, 'OPENWISP_UPDATE_CONFIG_MODEL', 'config.Device')
USER_COMMANDS = getattr(settings, 'OPENWISP_CONTROLLER_USER_COMMANDS', [])
