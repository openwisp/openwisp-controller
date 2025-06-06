from unittest import mock

from django.test import TransactionTestCase, override_settings
from geoip2 import errors
from swapper import load_model

from .. import settings as app_settings
from ..tests.utils import CreateDeviceMixin

Device = load_model("config", "Device")
WhoIsInfo = load_model("config", "WhoIsInfo")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")
Notification = load_model("openwisp_notifications", "Notification")

notification_qs = Notification.objects.all()


class TestWhoIsTransaction(CreateDeviceMixin, TransactionTestCase):
    _WHOIS_GEOIP_CLIENT = (
        "openwisp_controller.config.whois.service.geoip2_webservice.Client"
    )
    _WHOIS_TASKS_INFO_LOGGER = "openwisp_controller.config.whois.service.logger.info"
    _WHOIS_TASKS_WARN_LOGGER = "openwisp_controller.config.whois.service.logger.warning"
    _WHOIS_TASKS_ERR_LOGGER = "openwisp_controller.config.whois.service.logger.error"

    def setUp(self):
        self.admin = self._get_admin()

    def test_whois_enabled(self):
        org = self._get_org()
        OrganizationConfigSettings.objects.create(organization=org)

        with self.subTest("Test whois enabled set to True"):
            org.config_settings.whois_enabled = True
            self.assertEqual(getattr(org.config_settings, "whois_enabled"), True)

        with self.subTest("Test whois enabled set to False"):
            org.config_settings.whois_enabled = False
            self.assertEqual(getattr(org.config_settings, "whois_enabled"), False)

        with self.subTest("Test whois enabled set to None"):
            org.config_settings.whois_enabled = None
            org.config_settings.save(update_fields=["whois_enabled"])
            org.config_settings.refresh_from_db(fields=["whois_enabled"])
            self.assertEqual(
                getattr(org.config_settings, "whois_enabled"),
                app_settings.WHOIS_ENABLED,
            )

    @mock.patch(
        "openwisp_controller.config.whois.service.WhoIsService.fetch_whois_details.delay"  # noqa: E501
    )
    def test_task_called(self, mocked_task):
        org = self._get_org()
        OrganizationConfigSettings.objects.create(organization=org, whois_enabled=True)

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

        with self.subTest("task not called when last_ip is not changed"):
            device.last_ip = "10.0.0.1"
            device.save()
            mocked_task.assert_not_called()
        mocked_task.reset_mock()

        with self.subTest("task not called when whois is disabled"):
            Device.objects.all().delete()  # Clear existing devices
            org.config_settings.whois_enabled = False
            org.config_settings.save()
            device = self._create_device(last_ip="172.217.22.14")
            mocked_task.assert_not_called()
        mocked_task.reset_mock()

    # mocking the geoip2 client to return a mock response
    @mock.patch(_WHOIS_TASKS_INFO_LOGGER)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_whois_info_tasks(self, mock_client, mock_info):

        # helper function for asserting the model details with
        # mocked api response
        def _verify_whois_details(instance, ip_address):
            self.assertEqual(instance.organization_name, "Google LLC")
            self.assertEqual(instance.asn, "15169")
            self.assertEqual(instance.country, "United States")
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

        org = self._get_org()
        OrganizationConfigSettings.objects.create(organization=org, whois_enabled=True)

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

            _verify_whois_details(device.whois_service.get_whois_info(), device.last_ip)

        with self.subTest(
            "Test WhoIs create & deletion of old record when last ip is updated"
        ):
            old_ip_address = device.last_ip
            device.last_ip = "172.217.22.10"
            device.save()
            self.assertEqual(mock_info.call_count, 1)
            mock_info.reset_mock()
            device.refresh_from_db()

            _verify_whois_details(device.whois_service.get_whois_info(), device.last_ip)

            # details related to old ip address should be deleted
            self.assertEqual(
                WhoIsInfo.objects.filter(ip_address=old_ip_address).count(), 0
            )

        with self.subTest("Test WhoIs delete when device is deleted"):
            ip_address = device.last_ip
            device.delete(check_deactivated=False)
            self.assertEqual(mock_info.call_count, 0)
            mock_info.reset_mock()

            # whois related to the device's last_ip should be deleted
            self.assertEqual(WhoIsInfo.objects.filter(ip_address=ip_address).count(), 0)

    # we need to allow the task to propagate exceptions to ensure
    # `on_failure` method is called and notifications are executed
    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @mock.patch(_WHOIS_TASKS_ERR_LOGGER)
    @mock.patch(_WHOIS_TASKS_WARN_LOGGER)
    @mock.patch(_WHOIS_TASKS_INFO_LOGGER)
    def test_whois_task_failure_notification(self, mock_info, mock_warn, mock_error):
        org = self._get_org()
        OrganizationConfigSettings.objects.create(organization=org, whois_enabled=True)

        # we have 2 calls for error logging: 1 which is run by task for general errors
        # and one for generalized error logging for unexpected exceptions which
        # are not caught
        def assert_logging_on_exception(
            exception, info_calls=0, warn_calls=0, error_calls=2
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
