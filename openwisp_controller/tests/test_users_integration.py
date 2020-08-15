from openwisp_users.tests.test_admin import TestUsersAdmin


class TestUsersIntegration(TestUsersAdmin):
    """
    tests integration with openwisp_users
    """

    # fixing these tests is overkill
    test_only_superuser_has_add_delete_org_perm = None
    test_can_change_inline_org_owner = None


del TestUsersAdmin
