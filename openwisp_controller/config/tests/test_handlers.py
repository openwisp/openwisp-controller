from unittest.mock import patch

from django.test import TransactionTestCase

from .. import tasks
from .utils import CreateConfigMixin


class TestHandlers(CreateConfigMixin, TransactionTestCase):
    @patch.object(tasks.deactivate_organization_devices, "delay")
    @patch.object(tasks.invalidate_controller_views_cache, "delay")
    def test_organization_disabled_handler(self, mocked_invalidate, mocked_deactivate):
        with self.subTest("Test task not executed on creating active orgs"):
            org = self._create_org()
            mocked_invalidate.assert_not_called()
            mocked_deactivate.assert_not_called()

        with self.subTest("Test task executed on changing active to inactive org"):
            org.is_active = False
            org.save()
            mocked_invalidate.assert_called_once_with(str(org.id))
            mocked_deactivate.assert_called_once_with(str(org.id))

        mocked_invalidate.reset_mock()
        mocked_deactivate.reset_mock()
        with self.subTest("Test task not executed on saving inactive org"):
            org.name = "Changed named"
            org.save()
            mocked_invalidate.assert_not_called()
            mocked_deactivate.assert_not_called()

        with self.subTest("Test task not executed on creating inactive org"):
            inactive_org = self._create_org(
                is_active=False, name="inactive", slug="inactive"
            )
            mocked_invalidate.assert_not_called()
            mocked_deactivate.assert_not_called()

        with self.subTest("Test task not executed on changing inactive to active org"):
            inactive_org.is_active = True
            inactive_org.save()
            mocked_invalidate.assert_not_called()
            mocked_deactivate.assert_not_called()

    def test_deactivate_organization_devices(self):
        org = self._create_org()
        device = self._create_device(organization=org)
        config = self._create_config(device=device)
        device = config.device

        with self.subTest("Devices are deactivated when org gets disabled"):
            org.is_active = False
            org.save()
            tasks.deactivate_organization_devices(org.id)
            device.refresh_from_db()
            config.refresh_from_db()
            self.assertEqual(device._is_deactivated, True)
            self.assertEqual(config.status in ("deactivating", "deactivated"), True)

        with self.subTest("Re-enabling org does not reactivate devices"):
            org.is_active = True
            org.save()
            device.refresh_from_db()
            self.assertEqual(device._is_deactivated, True)
