from openwisp_controller.connection.tests.test_admin import TestAdmin as BaseTestAdmin
from openwisp_controller.connection.tests.test_models import (
    TestModels as BaseTestModels,
)
from openwisp_controller.connection.tests.test_models import (
    TestModelsTransaction as BaseTestModelsTransaction,
)
from openwisp_controller.connection.tests.test_notifications import (
    TestNotifications as BaseTestNotifications,
)
from openwisp_controller.connection.tests.test_notifications import (
    TestNotificationTransaction as BaseTestNotificationTransaction,
)
from openwisp_controller.connection.tests.test_ssh import TestSsh as BaseTestSsh
from openwisp_controller.connection.tests.test_tasks import TestTasks as BaseTestTasks


class TestAdmin(BaseTestAdmin):
    config_app_label = 'sample_config'
    app_label = 'sample_connection'


class TestModels(BaseTestModels):
    app_label = 'sample_connection'


class TestModelsTransaction(BaseTestModelsTransaction):
    app_label = 'sample_connection'


class TestTasks(BaseTestTasks):
    pass


class TestSsh(BaseTestSsh):
    pass


class TestNotifications(BaseTestNotifications):
    app_label = 'sample_connection'


class TestNotificationTransaction(BaseTestNotificationTransaction):
    app_label = 'sample_connection'


del BaseTestAdmin
del BaseTestModels
del BaseTestModelsTransaction
del BaseTestSsh
del BaseTestTasks
del BaseTestNotifications
del BaseTestNotificationTransaction
