from django.conf import settings

DEFAULT_CONNECTORS = (
    ("openwisp_controller.connection.connectors.ssh.Ssh", "SSH"),
    (
        "openwisp_controller.connection.connectors.openwrt.snmp.OpenWRTSnmp",
        "OpenWRT SNMP",
    ),
    (
        "openwisp_controller.connection.connectors.airos.snmp.AirOsSnmp",
        "Ubiquiti AirOS SNMP",
    ),
)

CONNECTORS = getattr(settings, "OPENWISP_CONNECTORS", DEFAULT_CONNECTORS)

DEFAULT_UPDATE_STRATEGIES = (
    ("openwisp_controller.connection.connectors.openwrt.ssh.OpenWrt", "OpenWRT SSH"),
    (
        "openwisp_controller.connection.connectors.openwrt.ssh.OpenWisp1",
        "OpenWISP 1.x SSH",
    ),
)

UPDATE_STRATEGIES = getattr(
    settings, "OPENWISP_UPDATE_STRATEGIES", DEFAULT_UPDATE_STRATEGIES
)

CONFIG_UPDATE_MAPPING = getattr(
    settings,
    "OPENWISP_CONFIG_UPDATE_MAPPING",
    {
        "netjsonconfig.OpenWrt": DEFAULT_UPDATE_STRATEGIES[0][0],
        "netjsonconfig.OpenWisp": DEFAULT_UPDATE_STRATEGIES[1][0],
    },
)

# How many results are listed per page on the mass command change page.
# Shared by the admin, which paginates with it, and by the websocket layer,
# which tells the browser the page a new result belongs to: the two have to
# agree or results are drawn on the wrong page.
BATCH_COMMAND_PAGE_SIZE = getattr(
    settings, "OPENWISP_CONTROLLER_BATCH_COMMAND_PAGE_SIZE", 20
)

SSH_AUTH_TIMEOUT = getattr(settings, "OPENWISP_SSH_AUTH_TIMEOUT", 2)
SSH_BANNER_TIMEOUT = getattr(settings, "OPENWISP_SSH_BANNER_TIMEOUT", 60)
SSH_COMMAND_TIMEOUT = getattr(settings, "OPENWISP_SSH_COMMAND_TIMEOUT", 30)
SSH_CONNECTION_TIMEOUT = getattr(settings, "OPENWISP_SSH_CONNECTION_TIMEOUT", 5)

# this may get overridden by openwisp-monitoring
UPDATE_CONFIG_MODEL = getattr(settings, "OPENWISP_UPDATE_CONFIG_MODEL", "config.Device")
USER_COMMANDS = getattr(settings, "OPENWISP_CONTROLLER_USER_COMMANDS", [])
ORGANIZATION_ENABLED_COMMANDS = getattr(
    settings, "OPENWISP_CONTROLLER_ORGANIZATION_ENABLED_COMMANDS", {"__all__": "*"}
)
MANAGEMENT_IP_ONLY = getattr(settings, "OPENWISP_CONTROLLER_MANAGEMENT_IP_ONLY", True)
