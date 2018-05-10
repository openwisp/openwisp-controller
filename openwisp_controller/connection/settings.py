from django.conf import settings

DEFAULT_CONNECTORS = (
    ('openwisp_controller.connection.connectors.ssh.Ssh', 'SSH'),
)

CONNECTORS = getattr(settings, 'OPENWISP_CONNECTORS', DEFAULT_CONNECTORS)

DEFAULT_UPDATE_STRATEGIES = (
    ('openwisp_controller.connection.connectors.openwrt.ssh.OpenWrt', 'OpenWRT SSH'),
)

UPDATE_STRATEGIES = getattr(settings, 'OPENWISP_UPDATE_STRATEGIES', DEFAULT_UPDATE_STRATEGIES)

CONFIG_UPDATE_MAPPING = getattr(settings, 'OPENWISP_CONFIG_UPDATE_MAPPING', {
    'netjsonconfig.OpenWrt': DEFAULT_UPDATE_STRATEGIES[0][0],
})
