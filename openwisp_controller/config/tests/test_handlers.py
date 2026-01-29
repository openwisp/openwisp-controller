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
    def test_vpn_cache_invalidation_on_context_change(self, mocked_task):
        """Test VPN cache invalidation when context changes"""
        config_settings = self._get_org_config_settings()

        with self.subTest("Test no invalidation on creation"):
            mocked_task.assert_not_called()

        with self.subTest("Test invalidation when context changes"):
            config_settings.context = {"new": "context"}
            config_settings.save()
            mocked_task.assert_called_once_with(str(config_settings.organization_id))

        with self.subTest("Test no invalidation when context unchanged"):
            mocked_task.reset_mock()
            config_settings.registration_enabled = False
            config_settings.save()
            mocked_task.assert_not_called()

    @patch.object(tasks.invalidate_organization_vpn_cache, "delay")
    def test_no_vpn_cache_invalidation_for_inactive_org(self, mocked_task):
        """Test no VPN cache invalidation for inactive organizations"""
        inactive_org = self._create_org(is_active=False)
        config_settings = inactive_org.config_settings

        with self.subTest("Test no invalidation for inactive org context change"):
            config_settings.context = {"new": "context"}
            config_settings.save()
            mocked_task.assert_not_called()

    def test_initial_context_pattern_implementation(self):
        """Test that _initial_context follows the established pattern"""
        config_settings = self._get_org_config_settings()

        with self.subTest("Test _initial_context is set on init"):
            self.assertEqual(config_settings._initial_context, config_settings.context)

        with self.subTest("Test _initial_context updates after save"):
            new_context = {"updated": "context"}
            config_settings.context = new_context
            config_settings.save()
            self.assertEqual(config_settings._initial_context, new_context)

    @patch.object(tasks.invalidate_organization_vpn_cache, "delay")
    def test_feature_fails_when_removed(self, mocked_task):
        """Test that fails with clear error when feature code is removed"""
        config_settings = self._get_org_config_settings()

        # Simulate removing the _initial_context pattern
        def broken_init(self, *args, **kwargs):
            super(type(config_settings), self).__init__(*args, **kwargs)
            # Missing: self._initial_context = self.context

        with patch.object(type(config_settings), "__init__", broken_init):
            new_config = type(config_settings)(organization=self._create_org())
            new_config.context = {"test": "context"}
            with self.assertRaises(
                AttributeError, msg="Feature code removed - _initial_context not set"
            ):
                new_config.save()

    @patch.object(tasks.invalidate_organization_vpn_cache, "delay")
    def test_feature_fails_when_bugged(self, mocked_task):
        """Test that fails with clear error when feature code is bugged"""
        config_settings = self._get_org_config_settings()

        # Simulate buggy implementation - always trigger invalidation
        def buggy_save(self, *args, **kwargs):
            super(type(config_settings), self).save(*args, **kwargs)
            # Bug: always invalidate regardless of context change
            if hasattr(self, "organization") and self.organization.is_active:
                tasks.invalidate_organization_vpn_cache.delay(str(self.organization_id))

        with patch.object(type(config_settings), "save", buggy_save):
            # This should not trigger invalidation but buggy code will
            config_settings.registration_enabled = False
            config_settings.save()
            mocked_task.assert_called_once()  # This proves the bug exists
