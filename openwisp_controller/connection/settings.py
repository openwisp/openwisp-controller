from django.conf import settings

CONNECTORS = getattr(settings, 'OPENWISP_CONNECTORS', (
    ('openwisp_controller.connection.connectors.ssh.Ssh', 'SSH'),
))

UPDATE_STRATEGIES = getattr(settings, 'OPENWISP_UPDATE_STRATEGIES', (
    ('openwisp_controller.connection.connectors.openwrt.ssh.OpenWrt', 'OpenWRT SSH'),
))

CONFIG_UPDATE_MAPPING = getattr(settings, 'OPENWISP_CONFIG_UPDATE_MAPPING', {
    'netjsonconfig.OpenWrt': UPDATE_STRATEGIES[0][0],
})
