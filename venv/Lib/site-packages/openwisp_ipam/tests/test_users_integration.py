from openwisp_users.tests.test_admin import TestUsersAdmin


class TestUsersIntegration(TestUsersAdmin):
    is_integration_test = True


del TestUsersAdmin
