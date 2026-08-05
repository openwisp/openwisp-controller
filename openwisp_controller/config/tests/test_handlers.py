from unittest.mock import patch

from django.test import TransactionTestCase

from .. import tasks
from .utils import CreateConfigMixin


class TestHandlers(CreateConfigMixin, TransactionTestCase):
    @patch("openwisp_controller.config.handlers.chain")
    def test_organization_disabled_handler(self, mocked_chain):
        with self.subTest("Test task not executed on creating active orgs"):
            org = self._create_org()
            mocked_chain.assert_not_called()

        with self.subTest("Test task executed on changing active to inactive org"):
            org.is_active = False
            org.save()
            mocked_chain.assert_called_once_with(
                tasks.deactivate_organization_devices.s(str(org.id)),
                tasks.invalidate_controller_views_cache.si(str(org.id)),
            )
            mocked_chain.return_value.delay.assert_called_once()

        mocked_chain.reset_mock()
        with self.subTest("Test task not executed on saving inactive org"):
            org.name = "Changed named"
            org.save()
            mocked_chain.assert_not_called()

        with self.subTest("Test task not executed on creating inactive org"):
            self._create_org(is_active=False, name="inactive", slug="inactive")
            mocked_chain.assert_not_called()

        with self.subTest("Test task not executed on changing inactive to active org"):
            org.is_active = True
            org.save()
            mocked_chain.assert_not_called()

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
