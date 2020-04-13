from openwisp_controller.pki.tests.test_admin import TestAdmin as BaseTestAdmin
from openwisp_controller.pki.tests.test_models import TestModels as BaseTestModels


class TestAdmin(BaseTestAdmin):
    app_label = 'sample_pki'


class TestModels(BaseTestModels):
    pass


del BaseTestAdmin
del BaseTestModels
