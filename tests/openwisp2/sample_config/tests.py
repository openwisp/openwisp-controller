from openwisp_controller.config.tests.test_admin import TestAdmin as BaseTestAdmin
from openwisp_controller.config.tests.test_config import TestConfig as BaseTestConfig
from openwisp_controller.config.tests.test_controller import (
    TestController as BaseTestController,
)
from openwisp_controller.config.tests.test_device import TestDevice as BaseTestDevice
from openwisp_controller.config.tests.test_tag import TestTag as BaseTestTag
from openwisp_controller.config.tests.test_template import (
    TestTemplate as BaseTestTemplate,
)
from openwisp_controller.config.tests.test_views import TestViews as BaseTestViews
from openwisp_controller.config.tests.test_vpn import TestVpn as BaseTestVpn


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


class TestViews(BaseTestViews):
    pass


class TestVpn(BaseTestVpn):
    pass


del BaseTestAdmin
del BaseTestConfig
del BaseTestController
del BaseTestDevice
del BaseTestTag
del BaseTestTemplate
del BaseTestViews
del BaseTestVpn
