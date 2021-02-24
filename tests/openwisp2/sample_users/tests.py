from openwisp_users.tests.test_admin import (
    TestBasicUsersIntegration as BaseTestBasicUsersIntegration,
)
from openwisp_users.tests.test_admin import (
    TestMultitenantAdmin as BaseTestMultitenantAdmin,
)
from openwisp_users.tests.test_admin import TestUsersAdmin as BaseTestUsersAdmin
from openwisp_users.tests.test_models import TestUsers as BaseTestUsers


class TestUsersAdmin(BaseTestUsersAdmin):
    app_label = 'sample_users'
    is_integration_test = True


class TestBasicUsersIntegration(BaseTestBasicUsersIntegration):
    app_label = 'sample_users'
    is_integration_test = True


class TestMultitenantAdmin(BaseTestMultitenantAdmin):
    app_label = 'sample_users'


class TestUsers(BaseTestUsers):
    pass


del BaseTestUsersAdmin
del BaseTestBasicUsersIntegration
del BaseTestMultitenantAdmin
del BaseTestUsers
