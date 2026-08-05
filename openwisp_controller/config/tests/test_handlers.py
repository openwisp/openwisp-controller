from unittest.mock import DEFAULT, patch

from django.test import TransactionTestCase

from .. import tasks
from .utils import CreateConfigMixin, Device


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

    def test_deactivate_organization_devices_partial_failure(self):
        org = self._create_org()
        failing_device = self._create_device(
            organization=org, name="failing-device", mac_address="00:11:22:33:44:01"
        )
        self._create_config(device=failing_device)
        ok_device = self._create_device(
            organization=org, name="ok-device", mac_address="00:11:22:33:44:02"
        )
        self._create_config(device=ok_device)
        with patch("openwisp_controller.config.handlers.chain"):
            org.is_active = False
            org.save()
        with patch.object(tasks, "logger") as mocked_logger:
            with patch.object(
                Device,
                "deactivate",
                autospec=True,
                wraps=Device.deactivate,
                side_effect=[Exception, DEFAULT],
            ):
                tasks.deactivate_organization_devices(org.id)
        mocked_logger.exception.assert_called_once_with(
            "Failed to deactivate device %s while disabling organization %s",
            failing_device.pk,
            org.id,
        )
        ok_device.refresh_from_db()
        self.assertEqual(ok_device._is_deactivated, True)
