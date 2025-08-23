import importlib
from io import StringIO
from unittest import mock

from django.contrib.gis.geos import Point
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management import call_command
from django.db.models.signals import post_delete, post_save
from django.test import TestCase, TransactionTestCase, override_settings, tag
from django.urls import reverse
from geoip2 import errors
from selenium.webdriver.common.by import By
from swapper import load_model

from openwisp_utils.tests import SeleniumTestMixin

from ...tests.utils import TestAdminMixin
from .. import settings as app_settings
from .handlers import connect_whois_handlers
from .tests_utils import CreateWHOISMixin, WHOISTransactionMixin

Device = load_model("config", "Device")
WHOISInfo = load_model("config", "WHOISInfo")
Notification = load_model("openwisp_notifications", "Notification")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")

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

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    def test_whois_details_device_api(self):
        """
        Test the WHOIS details API endpoint.
        """
        whois_obj = self._create_whois_info()
        device = self._create_device(last_ip=whois_obj.ip_address)
        self._login()

        with self.subTest(
            "Device List API has whois_info when WHOIS_CONFIGURED is True"
        ):
            response = self.client.get(reverse("config_api:device_list"))
            self.assertEqual(response.status_code, 200)
            self.assertIn("whois_info", response.data["results"][0])
            self.assertDictEqual(
                response.data["results"][0]["whois_info"],
                {
                    "isp": whois_obj.isp,
                    "country": whois_obj.address["country"],
                    "ip_address": whois_obj.ip_address,
                },
            )

        with self.subTest(
            "Device Detail API has whois_info when WHOIS_CONFIGURED is True"
        ):
            response = self.client.get(
                reverse("config_api:device_detail", args=[device.pk])
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("whois_info", response.data)
            api_whois_info = response.data["whois_info"]
            self.assertEqual(api_whois_info["isp"], whois_obj.isp)
            self.assertEqual(api_whois_info["cidr"], whois_obj.cidr)
            self.assertEqual(api_whois_info["asn"], whois_obj.asn)
            self.assertEqual(api_whois_info["timezone"], whois_obj.timezone)
            self.assertEqual(api_whois_info["address"], whois_obj.address)

        with self.subTest(
            "Device List API has whois_info as None when no WHOIS Info exists"
        ):
            device.last_ip = "172.217.22.24"
            device.save()
            response = self.client.get(reverse("config_api:device_list"))
            self.assertEqual(response.status_code, 200)
            self.assertIn("whois_info", response.data["results"][0])
            self.assertIsNone(response.data["results"][0]["whois_info"])

        with self.subTest(
            "Device Detail API has whois_info as None when no WHOIS Info exists"
        ):
            response = self.client.get(
                reverse("config_api:device_detail", args=[device.pk])
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("whois_info", response.data)
            self.assertIsNone(response.data["whois_info"])

        with mock.patch.object(app_settings, "WHOIS_CONFIGURED", False):
            with self.subTest(
                "Device List API has no whois_info when WHOIS_CONFIGURED is False"
            ):
                response = self.client.get(reverse("config_api:device_list"))
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("whois_info", response.data["results"][0])

            with self.subTest(
                "Device Detail API has no whois_info when WHOIS_CONFIGURED is False"
            ):
                response = self.client.get(
                    reverse("config_api:device_detail", args=[device.pk])
                )
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("whois_info", response.data)

    def test_last_ip_management_command(self):
        out = StringIO()
        device = self._create_device(last_ip="172.217.22.11")
        args = ["--noinput"]
        call_command("clear_last_ip", *args, stdout=out, stderr=StringIO())
        self.assertIn(
            "Cleared last IP addresses for 1 active device(s).", out.getvalue()
        )
        device.refresh_from_db()
        self.assertIsNone(device.last_ip)

        call_command("clear_last_ip", *args, stdout=out, stderr=StringIO())
        self.assertIn("No active devices with last IP to clear.", out.getvalue())


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

        # Common validation checks for longitude and latitude
        coordinates_cases = [
            (150.0, 100.0, "Latitude must be between -90 and 90 degrees."),
            (150.0, -100.0, "Latitude must be between -90 and 90 degrees."),
            (200.0, 80.0, "Longitude must be between -180 and 180 degrees."),
            (-200.0, -80.0, "Longitude must be between -180 and 180 degrees."),
        ]
        for longitude, latitude, expected_msg in coordinates_cases:
            with self.assertRaises(ValidationError) as context_manager:
                point = Point(longitude, latitude, srid=4326)
                self._create_whois_info(coordinates=point)
            try:
                self.assertEqual(
                    context_manager.exception.message_dict["coordinates"][0],
                    expected_msg,
                )
            except AssertionError:
                self.fail("ValidationError message not equal to expected message.")


class TestWHOISTransaction(
    CreateWHOISMixin, WHOISTransactionMixin, TransactionTestCase
):
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
    def test_whois_task_called(self, mocked_lookup_task):
        connect_whois_handlers()
        self._task_called(mocked_lookup_task)

        Device.objects.all().delete()  # Clear existing devices
        device = self._create_device()
        with self.subTest(
            "WHOIS lookup task not called when last_ip has related WhoIsInfo"
        ):
            device.organization.config_settings.whois_enabled = True
            device.organization.config_settings.save()
            device.last_ip = "172.217.22.14"
            self._create_whois_info(ip_address=device.last_ip)
            device.save()
            mocked_lookup_task.assert_not_called()
        mocked_lookup_task.reset_mock()

        with self.subTest(
            "WHOIS lookup task not called via DeviceChecksumView when "
            "last_ip has related WhoIsInfo"
        ):
            WHOISInfo.objects.all().delete()
            self._create_whois_info(ip_address=device.last_ip)
            self._create_config(device=device)
            response = self.client.get(
                reverse("controller:device_checksum", args=[device.pk]),
                {"key": device.key},
                REMOTE_ADDR=device.last_ip,
            )
            self.assertEqual(response.status_code, 200)
            mocked_lookup_task.assert_not_called()
        mocked_lookup_task.reset_mock()

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
            device1.refresh_from_db()
            self.assertEqual(response.status_code, 200)
            mocked_task.assert_called()
            mocked_task.reset_mock()
            response = self.client.get(
                reverse("controller:device_checksum", args=[device2.pk]),
                {"key": device2.key},
                REMOTE_ADDR="172.217.22.30",
            )
            device2.refresh_from_db()
            self.assertEqual(response.status_code, 200)
            mocked_task.assert_not_called()
            mocked_task.reset_mock()

        with self.subTest(
            "Task not called via DeviceChecksumView when a device has no WHOIS record"
        ):
            WHOISInfo.objects.all().delete()
            response = self.client.get(
                reverse("controller:device_checksum", args=[device1.pk]),
                {"key": device1.key},
                REMOTE_ADDR=device1.last_ip,
            )
            self.assertEqual(response.status_code, 200)
            mocked_task.assert_not_called()
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
            self.assertEqual(instance.coordinates.x, 150.0)
            self.assertEqual(instance.coordinates.y, 50.0)

        # mocking the response from the geoip2 client
        mock_client.return_value.city.return_value = self._mocked_client_response()

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
            " when no other devices are linked to the old ip address"
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

        with self.subTest(
            "Test WHOIS create & deletion of old record when last ip is updated"
            " when other devices are linked to the old ip address"
        ):
            old_ip_address = device.last_ip
            self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.11",
            )
            device.last_ip = "172.217.22.11"
            device.save()
            self.assertEqual(mock_info.call_count, 1)
            mock_info.reset_mock()
            device.refresh_from_db()

            _verify_whois_details(
                device.whois_service.get_device_whois_info(), device.last_ip
            )

            # details related to old ip address should be not be deleted
            self.assertEqual(
                WHOISInfo.objects.filter(ip_address=old_ip_address).count(), 1
            )

        with self.subTest(
            "Test WHOIS not deleted when device is deleted and"
            " other active devices are linked to the last_ip"
        ):
            ip_address = device.last_ip
            device.delete(check_deactivated=False)
            self.assertEqual(mock_info.call_count, 0)
            mock_info.reset_mock()

            # WHOIS related to the device's last_ip should be deleted
            self.assertEqual(WHOISInfo.objects.filter(ip_address=ip_address).count(), 1)

        Device.objects.all().delete()
        with self.subTest(
            "Test WHOIS deleted when device is deleted and"
            " no other active devices are linked to the last_ip"
        ):
            device1 = self._create_device(last_ip="172.217.22.11")
            device2 = self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.11",
            )
            device2.deactivate()
            mock_info.reset_mock()
            ip_address = device1.last_ip
            device1.delete(check_deactivated=False)
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
                self.assertEqual(notification.level, "error")
                self.assertEqual(notification.type, "generic_message")
                self.assertIn(
                    "Failed to fetch WHOIS details for device",
                    notification.message,
                )
                self.assertIn(device.last_ip, notification.rendered_description)

            mock_info.reset_mock()
            mock_warn.reset_mock()
            mock_error.reset_mock()
            notification_qs.delete()

        # Test for all possible exceptions that can be raised by the geoip2 client
        assert_logging_on_exception(errors.OutOfQueriesError)
        assert_logging_on_exception(errors.AddressNotFoundError)
        assert_logging_on_exception(errors.AuthenticationError)
        assert_logging_on_exception(errors.PermissionRequiredError)


@tag("selenium_tests")
class TestWHOISSelenium(CreateWHOISMixin, SeleniumTestMixin, StaticLiveServerTestCase):
    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    def test_whois_device_admin(self):
        def no_console_warnings():
            for error in self.get_browser_logs():
                if error["level"] == "WARNING" and error["message"] not in [
                    "wrong event specified: touchleave"
                ]:
                    self.fail(f'Browser console error: {error["message"]}')

        whois_obj = self._create_whois_info()
        device = self._create_device(last_ip=whois_obj.ip_address)
        self.login()

        with self.subTest(
            "WHOIS details visible in device admin when WHOIS_CONFIGURED is True"
        ):
            self.open(reverse("admin:config_device_change", args=[device.pk]))
            table = self.find_element(By.CSS_SELECTOR, "table.whois-table")
            rows = table.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                if cells := row.find_elements(By.TAG_NAME, "td"):
                    self.assertEqual(cells[0].text, whois_obj.isp)
                    self.assertEqual(cells[1].text, whois_obj.address["country"])

            details = self.find_element(By.CSS_SELECTOR, "details.whois")
            self.web_driver.execute_script(
                "arguments[0].setAttribute('open','')", details
            )
            additional_text = details.find_elements(By.CSS_SELECTOR, ".additional-text")
            self.assertIn(whois_obj.asn, additional_text[0].text)
            self.assertIn(whois_obj.timezone, additional_text[1].text)
            self.assertIn(whois_obj.formatted_address, additional_text[2].text)
            self.assertIn(whois_obj.cidr, additional_text[3].text)
            no_console_warnings()

        with mock.patch.object(app_settings, "WHOIS_CONFIGURED", False):
            with self.subTest(
                "WHOIS details not visible in device admin "
                + "when WHOIS_CONFIGURED is False"
            ):
                self.open(reverse("admin:config_device_change", args=[device.pk]))
                self.wait_for_invisibility(By.CSS_SELECTOR, "table.whois-table")
                self.wait_for_invisibility(By.CSS_SELECTOR, "details.whois")
                no_console_warnings()

        with self.subTest(
            "WHOIS details not visible in device admin when WHOIS is disabled"
        ):
            org = self._get_org()
            org.config_settings.whois_enabled = False
            org.config_settings.save(update_fields=["whois_enabled"])
            self.open(reverse("admin:config_device_change", args=[device.pk]))
            self.wait_for_invisibility(By.CSS_SELECTOR, "table.whois-table")
            self.wait_for_invisibility(By.CSS_SELECTOR, "details.whois")
            no_console_warnings()

        with self.subTest(
            "WHOIS details not visible in device admin when WHOIS Info does not exist"
        ):
            org = self._get_org()
            org.config_settings.whois_enabled = True
            org.config_settings.save(update_fields=["whois_enabled"])
            WHOISInfo.objects.all().delete()
            self.open(reverse("admin:config_device_change", args=[device.pk]))
            self.wait_for_invisibility(By.CSS_SELECTOR, "table.whois-table")
            self.wait_for_invisibility(By.CSS_SELECTOR, "details.whois")
            no_console_warnings()
