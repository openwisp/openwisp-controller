from openwisp_controller.config.admin import OrganizationLimitsInline
from openwisp_users.tests.test_admin import TestUsersAdmin

from .mixins import GetEditFormInlineMixin


class TestUsersIntegration(GetEditFormInlineMixin, TestUsersAdmin):
    """
    tests integration with openwisp_users
    """

    is_integration_test = True

    def _get_disabled_org_test_excluded_inline(self):
        inlines = super()._get_disabled_org_test_excluded_inline()
        inlines += [OrganizationLimitsInline]
        return inlines


del TestUsersAdmin
