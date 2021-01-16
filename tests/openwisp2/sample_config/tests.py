from openwisp_controller.config.tests.test_admin import TestAdmin as BaseTestAdmin
from openwisp_controller.config.tests.test_app import (
    TestCustomAdminDashboard as BaseTestCustomAdminDashboard,
)
from openwisp_controller.config.tests.test_config import TestConfig as BaseTestConfig
from openwisp_controller.config.tests.test_controller import (
    TestController as BaseTestController,
)
from openwisp_controller.config.tests.test_device import TestDevice as BaseTestDevice
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


class TestAdmin(BaseTestAdmin):
    app_label = 'sample_config'


class TestConfig(BaseTestConfig):
    pass


class TestController(BaseTestController):
    pass


class TestDevice(BaseTestDevice):
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


class TestCustomAdminDashboard(BaseTestCustomAdminDashboard):
    pass


del BaseTestAdmin
del BaseTestConfig
del BaseTestController
del BaseTestDevice
del BaseTestTag
del BaseTestTemplate
del BaseTestTemplateTransaction
del BaseTestNotifications
del BaseTestViews
del BaseTestVpn
del BaseTestVpnTransaction
del BaseTestCustomAdminDashboard
