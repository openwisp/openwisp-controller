from openwisp_controller.config.tests.test_apps import TestApps as BaseTestApps
from openwisp_controller.geo.tests.test_admin import TestAdmin as BaseTestAdmin
from openwisp_controller.geo.tests.test_admin_inline import (
    TestAdminInline as BaseTestAdminInline,
)
from openwisp_controller.geo.tests.test_api import TestApi as BaseTestApi
from openwisp_controller.geo.tests.test_models import TestModels as BaseTestModels


class TestAdmin(BaseTestAdmin):
    app_label = 'sample_geo'


class TestAdminInline(BaseTestAdminInline):
    app_label = 'sample_geo'


class TestApi(BaseTestApi):
    pass


class TestApps(BaseTestApps):
    pass


class TestModels(BaseTestModels):
    pass


del BaseTestAdmin
del BaseTestAdminInline
del BaseTestApi
del BaseTestApps
del BaseTestModels
