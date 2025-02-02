from unittest.mock import patch

from openwisp_controller.tests.mixins import GetEditFormInlineMixin
from openwisp_users.tests.test_admin import (
    TestBasicUsersIntegration as BaseTestBasicUsersIntegration,
)
from openwisp_users.tests.test_admin import (
    TestMultitenantAdmin as BaseTestMultitenantAdmin,
)
from openwisp_users.tests.test_admin import TestUsersAdmin as BaseTestUsersAdmin
from openwisp_users.tests.test_models import TestUsers as BaseTestUsers

additional_fields = [
    ('social_security_number', '123-45-6789'),
]


class TestUsersAdmin(GetEditFormInlineMixin, BaseTestUsersAdmin):
    app_label = 'sample_users'
    is_integration_test = True
    _additional_user_fields = additional_fields


class TestBasicUsersIntegration(GetEditFormInlineMixin, BaseTestBasicUsersIntegration):
    app_label = 'sample_users'
    is_integration_test = True
    _additional_user_fields = additional_fields


class TestMultitenantAdmin(BaseTestMultitenantAdmin):
    app_label = 'sample_users'


class TestUsers(BaseTestUsers):
    # This task access the organizations_dict when user is created.
    # This makes the test fail because the cache is already populated.
    @patch('openwisp_notifications.tasks.create_superuser_notification_settings')
    @patch('openwisp_notifications.tasks.superuser_demoted_notification_setting')
    def test_organizations_dict_cache(self, *args):
        super().test_organizations_dict_cache()


del BaseTestUsersAdmin
del BaseTestBasicUsersIntegration
del BaseTestMultitenantAdmin
del BaseTestUsers
