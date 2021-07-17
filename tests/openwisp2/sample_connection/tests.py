from openwisp_controller.connection.tests.test_admin import (
    TestCommandInlines as BaseTestCommandInlines,
)
from openwisp_controller.connection.tests.test_admin import (
    TestConnectionAdmin as BaseTestConnectionAdmin,
)
from openwisp_controller.connection.tests.test_api import (
    TestConnectionApi as BaseTestConnectionApi,
)
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


class TestConnectionAdmin(BaseTestConnectionAdmin):
    config_app_label = 'sample_config'
    app_label = 'sample_connection'


class TestCommandInlines(BaseTestCommandInlines):
    config_app_label = 'sample_config'


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


class TestConnectionApi(BaseTestConnectionApi):
    pass


del BaseTestCommandInlines
del BaseTestConnectionAdmin
del BaseTestModels
del BaseTestModelsTransaction
del BaseTestSsh
del BaseTestTasks
del BaseTestNotifications
del BaseTestNotificationTransaction
del BaseTestConnectionApi
