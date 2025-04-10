from openwisp_controller.config.tests.test_admin import TestAdmin as BaseTestAdmin
from openwisp_controller.config.tests.test_admin import (
    TestDeviceGroupAdmin as BaseTestDeviceGroupAdmin,
)
from openwisp_controller.config.tests.test_admin import (
    TestDeviceGroupAdminTransaction as BaseTestDeviceGroupAdminTransaction,
)
from openwisp_controller.config.tests.test_admin import (
    TestTransactionAdmin as BaseTestTransactionAdmin,
)
from openwisp_controller.config.tests.test_api import TestConfigApi as BaseTestConfigApi
from openwisp_controller.config.tests.test_apps import TestApps as BaseTestApps
from openwisp_controller.config.tests.test_config import TestConfig as BaseTestConfig
from openwisp_controller.config.tests.test_config import (
    TestTransactionConfig as BaseTestTransactionConfig,
)
from openwisp_controller.config.tests.test_controller import (
    TestController as BaseTestController,
)
from openwisp_controller.config.tests.test_device import TestDevice as BaseTestDevice
from openwisp_controller.config.tests.test_device_group import (
    TestDeviceGroup as BaseTestDeviceGroup,
)
from openwisp_controller.config.tests.test_notifications import (
    TestNotifications as BaseTestNotifications,
)
from openwisp_controller.config.tests.test_tag import TestTag as BaseTestTag
from openwisp_controller.config.tests.test_template import (
    TestTemplate as BaseTestTemplate,
)
from openwisp_controller.config.tests.test_template import (
    TestTemplateTransaction as BaseTestTemplateTransaction,
)
from openwisp_controller.config.tests.test_views import TestViews as BaseTestViews
from openwisp_controller.config.tests.test_vpn import TestVpn as BaseTestVpn
from openwisp_controller.config.tests.test_vpn import (
    TestVpnTransaction as BaseTestVpnTransaction,
)
from openwisp_controller.config.tests.test_vpn import TestVxlan as BaseTestVxlan
from openwisp_controller.config.tests.test_vpn import TestWireguard as BaseTestWireguard


class TestAdmin(BaseTestAdmin):
    app_label = 'sample_config'


class TestTransactionAdmin(BaseTestTransactionAdmin):
    app_label = 'sample_config'
    _deactivated_device_expected_readonly_fields = 23


class TestDeviceGroupAdmin(BaseTestDeviceGroupAdmin):
    app_label = 'sample_config'


class TestDeviceGroupAdminTransaction(BaseTestDeviceGroupAdminTransaction):
    app_label = 'sample_config'


class TestConfig(BaseTestConfig):
    pass


class TestTransactionConfig(BaseTestTransactionConfig):
    pass


class TestController(BaseTestController):
    pass


class TestDevice(BaseTestDevice):
    pass


class TestDeviceGroup(BaseTestDeviceGroup):
    pass


class TestTag(BaseTestTag):
    pass


class TestTemplate(BaseTestTemplate):
    pass


class TestTemplateTransaction(BaseTestTemplateTransaction):
    pass


class TestNotifications(BaseTestNotifications):
    app_label = 'sample_config'


class TestViews(BaseTestViews):
    pass


class TestVpn(BaseTestVpn):
    pass


class TestVpnTransaction(BaseTestVpnTransaction):
    pass


class TestApps(BaseTestApps):
    pass


class TestConfigApi(BaseTestConfigApi):
    pass


class TestWireguard(BaseTestWireguard):
    pass


class TestVxlan(BaseTestVxlan):
    pass


del BaseTestAdmin
del BaseTestTransactionAdmin
del BaseTestDeviceGroupAdmin
del BaseTestDeviceGroupAdminTransaction
del BaseTestConfig
del BaseTestTransactionConfig
del BaseTestController
del BaseTestDevice
del BaseTestDeviceGroup
del BaseTestTag
del BaseTestTemplate
del BaseTestTemplateTransaction
del BaseTestNotifications
del BaseTestViews
del BaseTestVpn
del BaseTestVpnTransaction
del BaseTestApps
del BaseTestConfigApi
del BaseTestWireguard
del BaseTestVxlan
