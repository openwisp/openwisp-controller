from unittest.mock import patch

from django.test import TestCase

from openwisp_users.tests.utils import TestOrganizationMixin

from .. import tasks


class TestHandlers(TestOrganizationMixin, TestCase):
    @patch.object(tasks.invalidate_controller_views_cache, "delay")
    def test_organization_disabled_handler(self, mocked_task):
        with self.subTest("Test task not executed on creating active orgs"):
            org = self._create_org()
            mocked_task.assert_not_called()
        with self.subTest("Test task executed on changing active to inactive org"):
            org.is_active = False
            org.save()
            mocked_task.assert_called_once()
        with self.subTest("Test task not executed on changing inactive to active org"):
            mocked_task.reset_mock()
            inactive_org = self._create_org(is_active=False)
            mocked_task.assert_not_called()
            inactive_org.is_active = True
            inactive_org.save()
            mocked_task.assert_not_called()


class TestOrganizationConfigSettingsVpnCacheInvalidation(
    TestOrganizationMixin, TestCase
):
    def _get_org_config_settings(self, org=None):
        if not org:
            org = self._create_org()
        return org.config_settings

    @patch.object(tasks.invalidate_organization_vpn_cache, "delay")
    def test_vpn_cache_invalidated_on_context_change(self, mocked_task):
        """Test VPN cache invalidation when context changes"""
        config_settings = self._get_org_config_settings()
        config_settings.context = {"new": "context"}
        config_settings.save()
        mocked_task.assert_called_once_with(str(config_settings.organization_id))

    @patch.object(tasks.invalidate_organization_vpn_cache, "delay")
    def test_no_cache_invalidation_on_create(self, mocked_task):
        """Test no VPN cache invalidation on object creation"""
        self._get_org_config_settings()
        mocked_task.assert_not_called()

    @patch.object(tasks.invalidate_organization_vpn_cache, "delay")
    def test_no_cache_invalidation_for_inactive_org(self, mocked_task):
        """Test no VPN cache invalidation for inactive organizations"""
        inactive_org = self._create_org(is_active=False)
        config_settings = inactive_org.config_settings
        config_settings.context = {"new": "context"}
        config_settings.save()
        mocked_task.assert_not_called()

    @patch.object(tasks.invalidate_organization_vpn_cache, "delay")
    def test_no_cache_invalidation_if_context_unchanged(self, mocked_task):
        """Test no VPN cache invalidation when context is unchanged"""
        config_settings = self._get_org_config_settings()
        original_context = config_settings.context
        config_settings.registration_enabled = False
        config_settings.save()
        mocked_task.assert_not_called()
        # Verify context actually didn't change
        self.assertEqual(config_settings.context, original_context)
