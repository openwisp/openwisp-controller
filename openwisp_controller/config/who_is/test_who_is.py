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
from .handlers import connect_who_is_handlers
from .utils import CreateWhoIsMixin

Device = load_model("config", "Device")
WhoIsInfo = load_model("config", "WhoIsInfo")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")
Notification = load_model("openwisp_notifications", "Notification")

notification_qs = Notification.objects.all()


class TestWhoIsFeature(CreateWhoIsMixin, TestAdminMixin, TestCase):
    @override_settings(
        OPENWISP_CONTROLLER_WHO_IS_ENABLED=False,
        OPENWISP_CONTROLLER_GEOIP_ACCOUNT_ID=None,
        OPENWISP_CONTROLLER_GEOIP_LICENSE_KEY=None,
    )
    def test_who_is_configuration_setting(self):
        # disconnect previously connected signals on app start, if any
        self._disconnect_signals()
        # reload app_settings to apply the overridden settings
        importlib.reload(app_settings)

        with self.subTest("Test Signals not connected when WHO_IS_CONFIGURED is False"):
            # should not connect any handlers since WHO_IS_CONFIGURED is False
            connect_who_is_handlers()

            assert not any(
                "device.delete_who_is_info" in str(r[0]) for r in post_delete.receivers
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
            "Test WhoIs field hidden on admin when WHO_IS_CONFIGURED is False"
        ):
            self._login()
            url = reverse(
                "admin:openwisp_users_organization_change",
                args=[self._get_org().pk],
            )
            response = self.client.get(url)
            self.assertNotContains(response, 'name="config_settings-0-who_is_enabled"')

        with self.subTest(
            "Test ImproperlyConfigured raised when WHO_IS_CONFIGURED is False"
        ):
            with override_settings(OPENWISP_CONTROLLER_WHO_IS_ENABLED=True):
                with self.assertRaises(ImproperlyConfigured):
                    # reload app_settings to apply the overridden settings
                    importlib.reload(app_settings)

        with override_settings(
            OPENWISP_CONTROLLER_GEOIP_ACCOUNT_ID="test_account_id",
            OPENWISP_CONTROLLER_GEOIP_LICENSE_KEY="test_license_key",
        ):
            importlib.reload(app_settings)
            with self.subTest(
                "Test WHO_IS_CONFIGURED is True when both settings are set"
            ):
                self.assertTrue(app_settings.WHO_IS_CONFIGURED)

            with self.subTest(
                "Test WhoIs field visible on admin when WHO_IS_CONFIGURED is True"
            ):
                self._login()
                url = reverse(
                    "admin:openwisp_users_organization_change",
                    args=[self._get_org().pk],
                )
                response = self.client.get(url)
                self.assertContains(response, 'name="config_settings-0-who_is_enabled"')

    def test_who_is_enabled(self):
        org = self._get_org()
        org_settings_obj = OrganizationConfigSettings(
            organization=org, who_is_enabled=True
        )

        with self.subTest("Test WhoIs not configured does not allow enabling who_is"):
            with mock.patch.object(
                app_settings, "WHO_IS_CONFIGURED", False
            ), self.assertRaises(ValidationError):
                org_settings_obj.full_clean()

        # create org settings object with WHO_IS_CONFIGURED set to True
        with mock.patch.object(app_settings, "WHO_IS_CONFIGURED", True):
            org_settings_obj.full_clean()
            org_settings_obj.save()

        with self.subTest("Test setting who_is enabled to True"):
            org.config_settings.who_is_enabled = True
            org.config_settings.save(update_fields=["who_is_enabled"])
            org.config_settings.refresh_from_db(fields=["who_is_enabled"])
            self.assertEqual(getattr(org.config_settings, "who_is_enabled"), True)

        with self.subTest("Test setting who_is enabled to False"):
            org.config_settings.who_is_enabled = False
            org.config_settings.save(update_fields=["who_is_enabled"])
            org.config_settings.refresh_from_db(fields=["who_is_enabled"])
            self.assertEqual(getattr(org.config_settings, "who_is_enabled"), False)

        with self.subTest(
            "Test setting who_is enabled to None fallbacks to global setting"
        ):
            # reload app_settings to ensure latest settings are applied
            importlib.reload(app_settings)
            org.config_settings.who_is_enabled = None
            org.config_settings.save(update_fields=["who_is_enabled"])
            org.config_settings.refresh_from_db(fields=["who_is_enabled"])
            self.assertEqual(
                getattr(org.config_settings, "who_is_enabled"),
                app_settings.WHO_IS_ENABLED,
            )


class TestWhoIsInfoModel(CreateWhoIsMixin, TestCase):
    def test_who_is_model_fields_validation(self):
        """
        Test db_constraints and validators for WhoIsInfo model fields.
        """
        org = self._get_org()
        # using `create` to bypass `clean` method validation
        OrganizationConfigSettings.objects.create(organization=org, who_is_enabled=True)

        with self.assertRaises(ValidationError):
            self._create_who_is_info(isp="a" * 101)

        with self.assertRaises(ValidationError):
            self._create_who_is_info(ip_address="127.0.0.1")

        with self.assertRaises(ValidationError):
            self._create_who_is_info(timezone="a" * 36)

        with self.assertRaises(ValidationError):
            self._create_who_is_info(cidr="InvalidCIDR")

        with self.assertRaises(ValidationError):
            self._create_who_is_info(asn="InvalidASN")


class TestWhoIsTransaction(CreateWhoIsMixin, TransactionTestCase):
    _WHO_IS_GEOIP_CLIENT = (
        "openwisp_controller.config.who_is.service.geoip2_webservice.Client"
    )
    _WHO_IS_TASKS_INFO_LOGGER = "openwisp_controller.config.who_is.service.logger.info"
    _WHO_IS_TASKS_WARN_LOGGER = (
        "openwisp_controller.config.who_is.service.logger.warning"
    )
    _WHO_IS_TASKS_ERR_LOGGER = "openwisp_controller.config.who_is.service.logger.error"

    def setUp(self):
        self.admin = self._get_admin()

    @mock.patch.object(app_settings, "WHO_IS_CONFIGURED", True)
    @mock.patch(
        "openwisp_controller.config.who_is.service.WhoIsService.fetch_who_is_details.delay"  # noqa: E501
    )
    def test_task_called(self, mocked_task):
        org = self._get_org()
        OrganizationConfigSettings.objects.create(organization=org, who_is_enabled=True)
        connect_who_is_handlers()

        with self.subTest("task called when last_ip is public"):
            device = self._create_device(last_ip="172.217.22.14")
            mocked_task.assert_called()
        mocked_task.reset_mock()

        with self.subTest("task called when last_ip is changed and is public"):
            device.last_ip = "172.217.22.10"
            device.save()
            mocked_task.assert_called()
        mocked_task.reset_mock()

        with self.subTest("task not called when last_ip is private"):
            device.last_ip = "10.0.0.1"
            device.save()
            mocked_task.assert_not_called()
        mocked_task.reset_mock()

        with self.subTest("task not called when last_ip has related WhoIsInfo"):
            device.last_ip = "172.217.22.10"
            self._create_who_is_info(ip_address=device.last_ip)
            device.save()
            mocked_task.assert_not_called()
        mocked_task.reset_mock()

        with self.subTest("task not called when who_is is disabled"):
            Device.objects.all().delete()  # Clear existing devices
            org.config_settings.who_is_enabled = False
            # Invalidates old org config settings cache
            org.config_settings.save(update_fields=["who_is_enabled"])
            device = self._create_device(last_ip="172.217.22.14")
            mocked_task.assert_not_called()
        mocked_task.reset_mock()

        with self.subTest("task called via DeviceChecksumView when who_is is enabled"):
            org.config_settings.who_is_enabled = True
            # Invalidates old org config settings cache
            org.config_settings.save(update_fields=["who_is_enabled"])
            # config is required for checksum view to work
            self._create_config(device=device)
            # setting remote address field to a public IP
            response = self.client.get(
                reverse("controller:device_checksum", args=[device.pk]),
                {"key": device.key},
                REMOTE_ADDR="172.217.22.10",
            )
            self.assertEqual(response.status_code, 200)
            mocked_task.assert_called()
        mocked_task.reset_mock()

    # mocking the geoip2 client to return a mock response
    @mock.patch.object(app_settings, "WHO_IS_CONFIGURED", True)
    @mock.patch(_WHO_IS_TASKS_INFO_LOGGER)
    @mock.patch(_WHO_IS_GEOIP_CLIENT)
    def test_who_is_info_tasks(self, mock_client, mock_info):

        # helper function for asserting the model details with
        # mocked api response
        def _verify_who_is_details(instance, ip_address):
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

        org = self._get_org()
        OrganizationConfigSettings.objects.create(organization=org, who_is_enabled=True)

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

        # creating a device with a last public IP
        with self.subTest("Test WhoIs create when device is created"):
            device = self._create_device(last_ip="172.217.22.14")
            self.assertEqual(mock_info.call_count, 1)
            mock_info.reset_mock()
            device.refresh_from_db()

            _verify_who_is_details(
                device.who_is_service.get_device_who_is_info(), device.last_ip
            )

        with self.subTest(
            "Test WhoIs create & deletion of old record when last ip is updated"
        ):
            old_ip_address = device.last_ip
            device.last_ip = "172.217.22.10"
            device.save()
            self.assertEqual(mock_info.call_count, 1)
            mock_info.reset_mock()
            device.refresh_from_db()

            _verify_who_is_details(
                device.who_is_service.get_device_who_is_info(), device.last_ip
            )

            # details related to old ip address should be deleted
            self.assertEqual(
                WhoIsInfo.objects.filter(ip_address=old_ip_address).count(), 0
            )

        with self.subTest("Test WhoIs delete when device is deleted"):
            ip_address = device.last_ip
            device.delete(check_deactivated=False)
            self.assertEqual(mock_info.call_count, 0)
            mock_info.reset_mock()

            # who_is related to the device's last_ip should be deleted
            self.assertEqual(WhoIsInfo.objects.filter(ip_address=ip_address).count(), 0)

    # we need to allow the task to propagate exceptions to ensure
    # `on_failure` method is called and notifications are executed
    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @mock.patch.object(app_settings, "WHO_IS_CONFIGURED", True)
    @mock.patch(_WHO_IS_TASKS_ERR_LOGGER)
    @mock.patch(_WHO_IS_TASKS_WARN_LOGGER)
    @mock.patch(_WHO_IS_TASKS_INFO_LOGGER)
    def test_who_is_task_failure_notification(self, mock_info, mock_warn, mock_error):
        org = self._get_org()
        OrganizationConfigSettings.objects.create(organization=org, who_is_enabled=True)

        def assert_logging_on_exception(
            exception, info_calls=0, warn_calls=0, error_calls=1
        ):
            with self.subTest(
                f"Test notifications and logging when {exception.__name__} is raised"
            ), mock.patch(self._WHO_IS_GEOIP_CLIENT, side_effect=exception("test")):
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
                    "Failed to fetch WhoIs details for device",
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
