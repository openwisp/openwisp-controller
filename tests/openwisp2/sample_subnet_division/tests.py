from openwisp_controller.subnet_division.tests.test_admin import (
    TestDeviceAdmin as BaseTestDeviceAdmin,
)
from openwisp_controller.subnet_division.tests.test_admin import (
    TestIPAdmin as BaseTestIPAdmin,
)
from openwisp_controller.subnet_division.tests.test_admin import (
    TestSubnetAdmin as BaseTestSubnetAdmin,
)
from openwisp_controller.subnet_division.tests.test_models import (
    TestSubnetDivisionRule as BaseTestSubnetDivisionRule,
)


class TestDeviceAdmin(BaseTestDeviceAdmin):
    config_label = 'sample_config'


class TestSubnetAdmin(BaseTestSubnetAdmin):
    config_label = 'sample_config'


class TestSubnetDivsionRule(BaseTestSubnetDivisionRule):
    config_label = 'sample_config'


class TestIPAdmin(BaseTestIPAdmin):
    pass


del BaseTestDeviceAdmin
del BaseTestSubnetAdmin
del BaseTestSubnetDivisionRule
del BaseTestIPAdmin
