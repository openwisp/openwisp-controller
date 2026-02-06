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
        # Import the model directly to avoid issues with related manager
        from openwisp_controller.config.models import OrganizationConfigSettings

        config_settings, _ = OrganizationConfigSettings.objects.get_or_create(
            organization=org, defaults={"context": {}}
        )
        return config_settings

    @patch.object(tasks.invalidate_organization_vpn_cache, "delay")
    @patch.object(tasks.bulk_invalidate_config_get_cached_checksum, "delay")
    def test_vpn_cache_invalidated_on_context_change(
        self, config_cache_mock, vpn_cache_mock
    ):
        """Test VPN cache invalidation when context changes"""
        config_settings = self._get_org_config_settings()
        config_settings.context = {"new": "context"}
        with self.captureOnCommitCallbacks(execute=True):
            config_settings.save()
        vpn_cache_mock.assert_called_once_with(str(config_settings.organization_id))
        config_cache_mock.assert_called_once_with(
            {"device__organization_id": str(config_settings.organization_id)}
        )

    @patch.object(tasks.invalidate_organization_vpn_cache, "delay")
    @patch.object(tasks.bulk_invalidate_config_get_cached_checksum, "delay")
    def test_no_cache_invalidation_on_create(self, config_cache_mock, vpn_cache_mock):
        """Test no VPN cache invalidation on object creation"""
        with self.captureOnCommitCallbacks(execute=True):
            self._get_org_config_settings()
        vpn_cache_mock.assert_not_called()
        config_cache_mock.assert_not_called()

    @patch.object(tasks.invalidate_organization_vpn_cache, "delay")
    @patch.object(tasks.bulk_invalidate_config_get_cached_checksum, "delay")
    def test_no_cache_invalidation_for_inactive_org(
        self, config_cache_mock, vpn_cache_mock
    ):
        """Test no VPN cache invalidation for inactive organizations"""
        inactive_org = self._create_org(is_active=False)
        config_settings = self._get_org_config_settings(inactive_org)
        config_settings.context = {"new": "context"}
        with self.captureOnCommitCallbacks(execute=True):
            config_settings.save()
        vpn_cache_mock.assert_not_called()
        config_cache_mock.assert_not_called()

    @patch.object(tasks.invalidate_organization_vpn_cache, "delay")
    @patch.object(tasks.bulk_invalidate_config_get_cached_checksum, "delay")
    def test_no_cache_invalidation_if_context_unchanged(
        self, config_cache_mock, vpn_cache_mock
    ):
        """Test no VPN cache invalidation when context is unchanged"""
        config_settings = self._get_org_config_settings()
        original_context = config_settings.context
        config_settings.registration_enabled = False
        with self.captureOnCommitCallbacks(execute=True):
            config_settings.save()
        vpn_cache_mock.assert_not_called()
        config_cache_mock.assert_not_called()
        # Verify context actually didn't change
        self.assertEqual(config_settings.context, original_context)
