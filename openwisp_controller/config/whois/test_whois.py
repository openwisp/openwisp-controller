import importlib
from unittest import mock

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db.models.signals import post_delete, post_save
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from geoip2 import errors
from swapper import load_model

from ...tests.utils import TestAdminMixin
from .. import settings as app_settings
from .handlers import connect_whois_handlers
from .utils import CreateWHOISMixin

Device = load_model("config", "Device")
WHOISInfo = load_model("config", "WHOISInfo")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")
Notification = load_model("openwisp_notifications", "Notification")

notification_qs = Notification.objects.all()


class TestWHOIS(CreateWHOISMixin, TestAdminMixin, TestCase):
    # Signals are connected when apps are loaded,
    # and if WHOIS is Configured all related WHOIS
    # handlers are also connected. Thus we need to
    # disconnect them.
    def _disconnect_signals(self):
        post_delete.disconnect(
            WHOISInfo.device_whois_info_delete_handler,
            sender=Device,
            dispatch_uid="device.delete_whois_info",
        )
        post_save.disconnect(
            WHOISInfo.invalidate_org_settings_cache,
            sender=OrganizationConfigSettings,
            dispatch_uid="invalidate_org_config_cache_on_org_config_save",
        )
        post_delete.disconnect(
            WHOISInfo.invalidate_org_settings_cache,
            sender=OrganizationConfigSettings,
            dispatch_uid="invalidate_org_config_cache_on_org_config_delete",
        )

    @override_settings(
        OPENWISP_CONTROLLER_WHOIS_ENABLED=False,
        OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT=None,
        OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY=None,
    )
    def test_whois_configuration_setting(self):
        self._disconnect_signals()
        org = self._get_org()
        # reload app_settings to apply the overridden settings
        importlib.reload(app_settings)

        with self.subTest("Test Signals not connected when WHOIS_CONFIGURED is False"):
            # should not connect any handlers since WHOIS_CONFIGURED is False
            connect_whois_handlers()

            assert not any(
                "device.delete_whois_info" in str(r[0]) for r in post_delete.receivers
            )
            assert not any(
                "invalidate_org_config_cache_on_org_config_save" in str(r[0])
                for r in post_save.receivers
            )
            assert not any(
                "invalidate_org_config_cache_on_org_config_delete" in str(r[0])
                for r in post_delete.receivers
            )

        with self.subTest(
            "Test WHOIS field hidden on admin when WHOIS_CONFIGURED is False"
        ):
            self._login()
            url = reverse(
                "admin:openwisp_users_organization_change",
                args=[org.pk],
            )
            response = self.client.get(url)
            self.assertNotContains(response, 'name="config_settings-0-whois_enabled"')

        with self.subTest(
            "Test ImproperlyConfigured raised when WHOIS_CONFIGURED is False"
        ):
            with override_settings(OPENWISP_CONTROLLER_WHOIS_ENABLED=True):
                with self.assertRaises(ImproperlyConfigured):
                    # reload app_settings to apply the overridden settings
                    importlib.reload(app_settings)

        with override_settings(
            OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT="test_account_id",
            OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY="test_license_key",
        ):
            importlib.reload(app_settings)
            with self.subTest(
                "Test WHOIS_CONFIGURED is True when both settings are set"
            ):
                self.assertTrue(app_settings.WHOIS_CONFIGURED)

            with self.subTest("Test Signals connected when WHOIS_CONFIGURED is True"):
                connect_whois_handlers()

                assert any(
                    "device.delete_whois_info" in str(r[0])
                    for r in post_delete.receivers
                )
                assert any(
                    "invalidate_org_config_cache_on_org_config_save" in str(r[0])
                    for r in post_save.receivers
                )
                assert any(
                    "invalidate_org_config_cache_on_org_config_delete" in str(r[0])
                    for r in post_delete.receivers
                )

            with self.subTest(
                "Test WHOIS field visible on admin when WHOIS_CONFIGURED is True"
            ):
                self._login()
                url = reverse(
                    "admin:openwisp_users_organization_change",
                    args=[org.pk],
                )
                response = self.client.get(url)
                self.assertContains(response, 'name="config_settings-0-whois_enabled"')

    def test_whois_enabled(self):
        OrganizationConfigSettings.objects.all().delete()
        device = self._create_device()
        with self.subTest(
            "Test WHOIS fallback when Organization settings do not exist"
        ):
            self.assertEqual(
                device.whois_service.is_whois_enabled, app_settings.WHOIS_ENABLED
            )

        org_settings_obj = OrganizationConfigSettings(
            organization=self._get_org(), whois_enabled=True
        )

        with self.subTest("Test WHOIS not configured does not allow enabling WHOIS"):
            with mock.patch.object(
                app_settings, "WHOIS_CONFIGURED", False
            ), self.assertRaises(ValidationError) as context_manager:
                org_settings_obj.full_clean()
            try:
                self.assertEqual(
                    context_manager.exception.message_dict["whois_enabled"][0],
                    "WHOIS_GEOIP_ACCOUNT and WHOIS_GEOIP_KEY must be set "
                    + "before enabling WHOIS feature.",
                )
            except AssertionError:
                self.fail("ValidationError message not equal to expected message.")

        with mock.patch.object(app_settings, "WHOIS_CONFIGURED", True):
            org_settings_obj.full_clean()
            org_settings_obj.save()

        with self.subTest("Test setting WHOIS enabled to True"):
            org_settings_obj.whois_enabled = True
            org_settings_obj.save(update_fields=["whois_enabled"])
            org_settings_obj.refresh_from_db(fields=["whois_enabled"])
            self.assertEqual(getattr(org_settings_obj, "whois_enabled"), True)

        with self.subTest("Test setting WHOIS enabled to False"):
            org_settings_obj.whois_enabled = False
            org_settings_obj.save(update_fields=["whois_enabled"])
            org_settings_obj.refresh_from_db(fields=["whois_enabled"])
            self.assertEqual(getattr(org_settings_obj, "whois_enabled"), False)

        with self.subTest(
            "Test setting WHOIS enabled to None fallbacks to global setting"
        ):
            # reload app_settings to ensure latest settings are applied
            importlib.reload(app_settings)
            org_settings_obj.whois_enabled = None
            org_settings_obj.save(update_fields=["whois_enabled"])
            org_settings_obj.refresh_from_db(fields=["whois_enabled"])
            self.assertEqual(
                getattr(org_settings_obj, "whois_enabled"),
                app_settings.WHOIS_ENABLED,
            )


class TestWHOISInfoModel(CreateWHOISMixin, TestCase):
    def test_whois_model_fields_validation(self):
        """
        Test db_constraints and validators for WHOISInfo model fields.
        """
        with self.assertRaises(ValidationError):
            self._create_whois_info(isp="a" * 101)

        with self.assertRaises(ValidationError) as context_manager:
            self._create_whois_info(ip_address="127.0.0.1")
        try:
            self.assertEqual(
                context_manager.exception.message_dict["ip_address"][0],
                "WHOIS information cannot be created for private IP addresses.",
            )
        except AssertionError:
            self.fail("ValidationError message not equal to expected message.")

        with self.assertRaises(ValidationError):
            self._create_whois_info(timezone="a" * 36)

        with self.assertRaises(ValidationError) as context_manager:
            self._create_whois_info(cidr="InvalidCIDR")
        try:
            # Not using assertEqual here because we are adding error message raised by
            # ipaddress module to the ValidationError message.
            self.assertIn(
                "Invalid CIDR format: 'InvalidCIDR'",
                context_manager.exception.message_dict["cidr"][0],
            )
        except AssertionError:
            self.fail("ValidationError message not equal to expected message.")

        with self.assertRaises(ValidationError):
            self._create_whois_info(asn="InvalidASN")


class TestWHOISTransaction(CreateWHOISMixin, TransactionTestCase):
    _WHOIS_GEOIP_CLIENT = (
        "openwisp_controller.config.whois.tasks.geoip2_webservice.Client"
    )
    _WHOIS_TASKS_INFO_LOGGER = "openwisp_controller.config.whois.tasks.logger.info"
    _WHOIS_TASKS_WARN_LOGGER = "openwisp_controller.config.whois.tasks.logger.warning"
    _WHOIS_TASKS_ERR_LOGGER = "openwisp_controller.config.whois.tasks.logger.error"

    def setUp(self):
        super().setUp()
        self.admin = self._get_admin()

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch("openwisp_controller.config.whois.tasks.fetch_whois_details.delay")
    def test_whois_task_called(self, mocked_task):
        org = self._get_org()
        connect_whois_handlers()

        with self.subTest("task called when last_ip is public"):
            with mock.patch("django.core.cache.cache.set") as mocked_set:
                device = self._create_device(last_ip="172.217.22.14")
                mocked_task.assert_called()
                mocked_set.assert_called_once()
        mocked_task.reset_mock()

        with self.subTest("task called when last_ip is changed and is public"):
            with mock.patch("django.core.cache.cache.get") as mocked_get:
                device.last_ip = "172.217.22.10"
                device.save()
                mocked_task.assert_called()
                mocked_get.assert_called_once()
        mocked_task.reset_mock()

        with self.subTest("task not called when last_ip is private"):
            device.last_ip = "10.0.0.1"
            device.save()
            mocked_task.assert_not_called()
        mocked_task.reset_mock()

        with self.subTest("task not called when last_ip has related WHOISInfo"):
            device.last_ip = "172.217.22.10"
            self._create_whois_info(ip_address=device.last_ip)
            device.save()
            mocked_task.assert_not_called()
        mocked_task.reset_mock()

        with self.subTest("task not called when WHOIS is disabled"):
            Device.objects.all().delete()
            org.config_settings.whois_enabled = False
            # Invalidates old org config settings cache
            org.config_settings.save(update_fields=["whois_enabled"])
            device = self._create_device(last_ip="172.217.22.14")
            mocked_task.assert_not_called()
        mocked_task.reset_mock()

        with self.subTest("task called via DeviceChecksumView when WHOIS is enabled"):
            org.config_settings.whois_enabled = True
            # Invalidates old org config settings cache
            org.config_settings.save(update_fields=["whois_enabled"])
            # config is required for checksum view to work
            self._create_config(device=device)
            # setting remote address field to a public IP to trigger WHOIS task
            # since the view uses this header for tracking the device's IP
            response = self.client.get(
                reverse("controller:device_checksum", args=[device.pk]),
                {"key": device.key},
                REMOTE_ADDR="172.217.22.10",
            )
            self.assertEqual(response.status_code, 200)
            mocked_task.assert_called()
        mocked_task.reset_mock()

        with self.subTest(
            "task called via DeviceChecksumView when a device has no WHOIS record"
        ):
            WHOISInfo.objects.all().delete()
            response = self.client.get(
                reverse("controller:device_checksum", args=[device.pk]),
                {"key": device.key},
                REMOTE_ADDR=device.last_ip,
            )
            self.assertEqual(response.status_code, 200)
            mocked_task.assert_called()
        mocked_task.reset_mock()

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch("openwisp_controller.config.whois.tasks.fetch_whois_details.delay")
    def test_whois_multiple_orgs(self, mocked_task):
        org2 = self._create_org(name="test org2", slug="test-org2")
        OrganizationConfigSettings.objects.create(
            organization=org2, whois_enabled=False
        )

        with self.subTest("Test task calls when device created with public last_ip"):
            device1 = self._create_device(
                last_ip="172.217.22.10", organization=self._get_org()
            )
            mocked_task.assert_called()
            mocked_task.reset_mock()
            device2 = self._create_device(last_ip="172.217.22.11", organization=org2)
            mocked_task.assert_not_called()
            mocked_task.reset_mock()

        with self.subTest("Test task calls when last_ip is changed and is public"):
            device1.last_ip = "172.217.22.12"
            device1.save()
            mocked_task.assert_called()
            mocked_task.reset_mock()
            device2.last_ip = "172.217.22.13"
            mocked_task.assert_not_called()
            mocked_task.reset_mock()

        with self.subTest("Test fetching WHOIS details"):
            whois_obj1 = self._create_whois_info(ip_address=device1.last_ip)
            self._create_whois_info(ip_address=device2.last_ip)
            self.assertEqual(whois_obj1, device1.whois_service.get_device_whois_info())
            self.assertIsNone(device2.whois_service.get_device_whois_info())

        with self.subTest("Test task calls in DeviceChecksumView when last_ip changes"):
            # config is required for checksum view to work
            self._create_config(device=device1)
            self._create_config(device=device2)
            response = self.client.get(
                reverse("controller:device_checksum", args=[device1.pk]),
                {"key": device1.key},
                REMOTE_ADDR="172.217.22.20",
            )
            self.assertEqual(response.status_code, 200)
            mocked_task.assert_called()
            mocked_task.reset_mock()
            response = self.client.get(
                reverse("controller:device_checksum", args=[device2.pk]),
                {"key": device2.key},
                REMOTE_ADDR="172.217.22.30",
            )
            self.assertEqual(response.status_code, 200)
            mocked_task.assert_not_called()
            mocked_task.reset_mock()

        with self.subTest(
            "task called via DeviceChecksumView when a device has no WHOIS record"
        ):
            WHOISInfo.objects.all().delete()
            response = self.client.get(
                reverse("controller:device_checksum", args=[device1.pk]),
                {"key": device1.key},
                REMOTE_ADDR=device1.last_ip,
            )
            self.assertEqual(response.status_code, 200)
            mocked_task.assert_called()
            mocked_task.reset_mock()
            response = self.client.get(
                reverse("controller:device_checksum", args=[device2.pk]),
                {"key": device2.key},
                REMOTE_ADDR=device2.last_ip,
            )
            self.assertEqual(response.status_code, 200)
            mocked_task.assert_not_called()
            mocked_task.reset_mock()

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_WHOIS_TASKS_INFO_LOGGER)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_whois_creation(self, mock_client, mock_info):
        # helper function for asserting the model details with
        # mocked api response
        connect_whois_handlers()

        def _verify_whois_details(instance, ip_address):
            self.assertEqual(instance.isp, "Google LLC")
            self.assertEqual(instance.asn, "15169")
            self.assertEqual(instance.timezone, "America/Los_Angeles")
            self.assertEqual(
                instance.address,
                {
                    "city": "Mountain View",
                    "country": "United States",
                    "continent": "North America",
                    "postal": "94043",
                },
            )
            self.assertEqual(instance.cidr, "172.217.22.0/24")
            self.assertEqual(instance.ip_address, ip_address)
            self.assertEqual(
                instance.formatted_address,
                "Mountain View, United States, North America, 94043",
            )

        # mocking the response from the geoip2 client
        mock_response = mock.MagicMock()
        mock_response.city.name = "Mountain View"
        mock_response.country.name = "United States"
        mock_response.continent.name = "North America"
        mock_response.postal.code = "94043"
        mock_response.traits.autonomous_system_organization = "Google LLC"
        mock_response.traits.autonomous_system_number = 15169
        mock_response.traits.network = "172.217.22.0/24"
        mock_response.location.time_zone = "America/Los_Angeles"
        mock_client.return_value.city.return_value = mock_response

        with self.subTest("Test WHOIS create when device is created"):
            device = self._create_device(last_ip="172.217.22.14")
            self.assertEqual(mock_info.call_count, 1)
            mock_info.reset_mock()
            device.refresh_from_db()

            _verify_whois_details(
                device.whois_service.get_device_whois_info(), device.last_ip
            )

        with self.subTest(
            "Test WHOIS create & deletion of old record when last ip is updated"
        ):
            old_ip_address = device.last_ip
            device.last_ip = "172.217.22.10"
            device.save()
            self.assertEqual(mock_info.call_count, 1)
            mock_info.reset_mock()
            device.refresh_from_db()

            _verify_whois_details(
                device.whois_service.get_device_whois_info(), device.last_ip
            )

            # details related to old ip address should be deleted
            self.assertEqual(
                WHOISInfo.objects.filter(ip_address=old_ip_address).count(), 0
            )

        with self.subTest("Test WHOIS delete when device is deleted"):
            ip_address = device.last_ip
            device.delete(check_deactivated=False)
            self.assertEqual(mock_info.call_count, 0)
            mock_info.reset_mock()

            # WHOIS related to the device's last_ip should be deleted
            self.assertEqual(WHOISInfo.objects.filter(ip_address=ip_address).count(), 0)

    # we need to allow the task to propagate exceptions to ensure
    # `on_failure` method is called and notifications are executed
    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_WHOIS_TASKS_ERR_LOGGER)
    @mock.patch(_WHOIS_TASKS_WARN_LOGGER)
    @mock.patch(_WHOIS_TASKS_INFO_LOGGER)
    def test_whois_task_failure_notification(self, mock_info, mock_warn, mock_error):
        def assert_logging_on_exception(
            exception, info_calls=0, warn_calls=0, error_calls=1
        ):
            with self.subTest(
                f"Test notifications and logging when {exception.__name__} is raised"
            ), mock.patch(self._WHOIS_GEOIP_CLIENT, side_effect=exception("test")):
                Device.objects.all().delete()  # Clear existing devices
                device = self._create_device(last_ip="172.217.22.14")
                self.assertEqual(mock_info.call_count, info_calls)
                self.assertEqual(mock_warn.call_count, warn_calls)
                self.assertEqual(mock_error.call_count, error_calls)
                self.assertEqual(notification_qs.count(), 1)
                notification = notification_qs.first()
                self.assertEqual(notification.actor, device)
                self.assertEqual(notification.target, device)
                self.assertEqual(notification.type, "generic_message")
                self.assertIn(
                    "Failed to fetch WHOIS details for device",
                    notification.message,
                )
                self.assertIn(device.last_ip, notification.description)

            mock_info.reset_mock()
            mock_warn.reset_mock()
            mock_error.reset_mock()
            notification_qs.delete()

        # Test for all possible exceptions that can be raised by the geoip2 client
        assert_logging_on_exception(errors.OutOfQueriesError)
        assert_logging_on_exception(errors.AddressNotFoundError)
        assert_logging_on_exception(errors.AuthenticationError)
        assert_logging_on_exception(errors.PermissionRequiredError)
