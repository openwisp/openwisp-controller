from openwisp_controller.connection.tests.test_admin import TestAdmin as BaseTestAdmin
from openwisp_controller.connection.tests.test_models import (
    TestModels as BaseTestModels,
)
from openwisp_controller.connection.tests.test_ssh import TestSsh as BaseTestSsh


class TestAdmin(BaseTestAdmin):
    config_app_label = 'sample_config'
    app_label = 'sample_connection'


class TestModels(BaseTestModels):
    app_label = 'sample_connection'


class TestSsh(BaseTestSsh):
    pass


del BaseTestAdmin
del BaseTestModels
del BaseTestSsh
