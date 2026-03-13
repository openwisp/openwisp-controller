import copy
import importlib
from datetime import timedelta
from io import StringIO
from unittest import mock
from uuid import uuid4

from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management import CommandError, call_command
from django.db.models.signals import post_delete, post_save
from django.test import TestCase, TransactionTestCase, override_settings, tag
from django.urls import reverse
from django.utils import timezone
from geoip2 import errors
from requests.exceptions import RequestException
from selenium.common.exceptions import UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from swapper import load_model

from openwisp_utils.tests import SeleniumTestMixin

from ....tests.utils import TestAdminMixin
from ... import settings as app_settings
from ..handlers import connect_whois_handlers
from ..service import WHOISService
from ..tasks import delete_whois_record, fetch_whois_details
from ..utils import get_whois_info, send_whois_task_notification
from .utils import CreateWHOISMixin, WHOISTransactionMixin

Config = load_model("config", "Config")
Device = load_model("config", "Device")
WHOISInfo = load_model("config", "WHOISInfo")
Notification = load_model("openwisp_notifications", "Notification")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")

MODIFIED_CACHE = copy.deepcopy(settings.CACHES)
# add key_prefix to avoid conflicts in parallel tests
MODIFIED_CACHE["default"]["KEY_PREFIX"] = "whois_failure"


def _notification_qs():
    return Notification.objects.all()


# SESSION_ENGINE set to DB to avoid conflicts in parallel tests
@override_settings(SESSION_ENGINE="django.contrib.sessions.backends.db")
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
        self.addCleanup(importlib.reload, app_settings)
        # ensure organization exists for admin page checks
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

    def test_is_older_requires_timezone_aware(self):
        """Verify is_older raises TypeError for naive datetimes."""
        naive_dt = timezone.now().replace(tzinfo=None)
        with self.assertRaises(TypeError):
            WHOISService.is_older(naive_dt)

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
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
            self.assertEqual(
                context_manager.exception.message_dict["whois_enabled"][0],
                "WHOIS_GEOIP_ACCOUNT and WHOIS_GEOIP_KEY must be set "
                + "before enabling WHOIS feature.",
            )

        with self.subTest("Test setting WHOIS enabled to True"):
            org_settings_obj.whois_enabled = True
            org_settings_obj.full_clean()
            org_settings_obj.save(update_fields=["whois_enabled"])
            org_settings_obj.refresh_from_db(fields=["whois_enabled"])
            self.assertTrue(org_settings_obj.whois_enabled)

        with self.subTest("Test setting WHOIS enabled to False"):
            org_settings_obj.whois_enabled = False
            org_settings_obj.full_clean()
            org_settings_obj.save(update_fields=["whois_enabled"])
            org_settings_obj.refresh_from_db(fields=["whois_enabled"])
            self.assertFalse(org_settings_obj.whois_enabled)

        with self.subTest(
            "Test setting WHOIS enabled to None fallbacks to global setting"
        ):
            # reload app_settings to ensure latest settings are applied
            importlib.reload(app_settings)
            org_settings_obj.whois_enabled = None
            org_settings_obj.full_clean()
            org_settings_obj.save(update_fields=["whois_enabled"])
            org_settings_obj.refresh_from_db(fields=["whois_enabled"])
            self.assertEqual(
                org_settings_obj.whois_enabled,
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
            "Device List API does not have whois_info (removed to avoid N+1)"
        ):
            response = self.client.get(reverse("config_api:device_list"))
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("whois_info", response.data["results"][0])

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
            "Device List API does not have whois_info when no WHOIS Info exists"
        ):
            device.last_ip = "172.217.22.24"
            device.save()
            device.refresh_from_db()
            response = self.client.get(reverse("config_api:device_list"))
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("whois_info", response.data["results"][0])

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

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    def test_device_list_api_whois_no_nplus1(self):
        """
        Test that WHOIS info doesn't cause N+1 queries in device list API.
        Should use constant queries regardless of device count.
        """
        self._login()
        path = reverse("config_api:device_list")
        # Create 3 devices with WHOIS info
        for i in range(3):
            device = self._create_device(
                name=f"device{i}",
                mac_address=f"00:11:22:33:44:{i:02x}",
                last_ip=f"172.217.22.{i + 1}",
            )
            WHOISInfo.objects.create(
                ip_address=device.last_ip,
                isp="Test ISP",
                asn="12345",
                address={"city": "Test City", "country": "Test Country"},
                cidr=f"172.217.22.{i + 1}/32",
            )
            with self.subTest(f"Device List API with WHOIS info: {i}"):
                with self.assertNumQueries(4):
                    response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.data["results"]), i + 1)
                for result in response.data["results"]:
                    self.assertNotIn("whois_info", result)

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    def test_last_ip_management_command(self):
        out = StringIO()
        device = self._create_device(last_ip="172.217.22.11")
        args = ["--noinput"]
        call_command("clear_last_ip", *args, stdout=out, stderr=StringIO())
        self.assertIn(
            "Cleared the last IP addresses for 1 active device(s).", out.getvalue()
        )
        device.refresh_from_db()
        self.assertIsNone(device.last_ip)
        out.seek(0)
        out.truncate(0)
        call_command("clear_last_ip", *args, stdout=out, stderr=StringIO())
        self.assertIn("No active devices with last IP to clear.", out.getvalue())

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    def test_last_ip_management_command_queries(self):
        out = StringIO()
        self._create_device(last_ip="172.217.22.11")
        self._create_device(
            name="default.test.device2",
            last_ip="172.217.22.12",
            mac_address="11:22:33:44:55:66",
        )
        self._create_device(
            name="default.test.device3",
            last_ip="172.217.22.13",
            mac_address="22:33:44:55:66:77",
        )
        self._create_device(
            name="default.test.device4", mac_address="66:33:44:55:66:77"
        )
        args = ["--noinput"]
        # 4 queries (3 for each device's last_ip update) and 1 for fetching devices
        with self.assertNumQueries(4):
            call_command("clear_last_ip", *args, stdout=out, stderr=StringIO())

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    def test_last_ip_management_command_invalidates_cache(self):
        device = self._create_device(last_ip="172.217.22.11")
        self._create_config(device=device)
        call_command("clear_last_ip", "--noinput", stdout=StringIO())
        device.refresh_from_db()
        self.assertEqual(device.last_ip, None)
        # We will use the DeviceChecksumView to set the last_ip again to
        # the same value to verify that the command invalidates the cache
        # and the view is able to send the same IP again.
        response = self.client.get(
            reverse("controller:device_checksum", args=[device.pk]),
            {"key": device.key},
            REMOTE_ADDR="172.217.22.11",
        )
        self.assertEqual(response.status_code, 200)
        device.refresh_from_db()
        self.assertEqual(device.last_ip, "172.217.22.11")

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", False)
    def test_clear_last_ip_command_not_enabled(self):
        """Test that clear_last_ip command raises error when WHOIS is not configured."""
        out = StringIO()
        err = StringIO()
        with self.assertRaises(CommandError) as context:
            call_command("clear_last_ip", "--noinput", stdout=out, stderr=err)
        self.assertIn("WHOIS lookup is not configured", str(context.exception))


class TestWHOISInfoModel(CreateWHOISMixin, TestCase):
    def test_whois_model_fields_validation(self):
        """
        Test db_constraints and validators for WHOISInfo model fields.
        """
        with self.assertRaises(ValidationError):
            self._create_whois_info(isp="a" * 101)
        with self.assertRaises(ValidationError) as context_manager:
            self._create_whois_info(ip_address="127.0.0.1")
        self.assertEqual(
            context_manager.exception.message_dict["ip_address"][0],
            "WHOIS information cannot be created for private IP addresses.",
        )
        with self.assertRaises(ValidationError):
            self._create_whois_info(timezone="a" * 36)
        with self.assertRaises(ValidationError) as context_manager:
            self._create_whois_info(cidr="InvalidCIDR")
        # Not using assertEqual here because we are adding error message raised by
        # ipaddress module to the ValidationError message.
        self.assertIn(
            "Invalid CIDR format: 'InvalidCIDR'",
            context_manager.exception.message_dict["cidr"][0],
        )
        with self.assertRaises(ValidationError):
            self._create_whois_info(asn="InvalidASNNumber")
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
            self.assertEqual(
                context_manager.exception.message_dict["coordinates"][0],
                expected_msg,
            )


# SESSION_ENGINE set to DB to avoid conflicts in parallel tests
@override_settings(SESSION_ENGINE="django.contrib.sessions.backends.db")
class TestWHOISTransaction(
    CreateWHOISMixin, WHOISTransactionMixin, TransactionTestCase
):
    _WHOIS_GEOIP_CLIENT = (
        "openwisp_controller.config.whois.service.geoip2_webservice.Client"
    )
    _WHOIS_TASKS_INFO_LOGGER = "openwisp_controller.config.whois.tasks.logger.info"
    _WHOIS_TASKS_WARN_LOGGER = "openwisp_controller.config.whois.tasks.logger.warning"
    _WHOIS_TASKS_ERR_LOGGER = "openwisp_controller.config.whois.tasks.logger.error"
    _WHOIS_TASK_NAME = "openwisp_controller.config.whois.tasks.fetch_whois_details"

    def setUp(self):
        super().setUp()
        self.admin = self._get_admin()

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_process_whois_details_handles_missing_coordinates(self, mock_client):
        """Ensure WHOIS processing tolerates missing coordinates in response."""
        connect_whois_handlers()
        mocked_response = self._mocked_client_response()
        # simulate missing coordinates
        mocked_response.location = None
        mock_client.return_value.city.return_value = mocked_response
        device = self._create_device(last_ip="172.217.22.14")
        whois_details = device.whois_service.process_whois_details(device.last_ip)
        self.assertIsNone(whois_details.get("coordinates"))

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch("openwisp_controller.config.whois.tasks.fetch_whois_details.delay")
    def test_whois_task_called(self, mocked_lookup_task):
        connect_whois_handlers()
        self._task_called(mocked_lookup_task)
        Device.objects.all().delete()
        WHOISInfo.objects.all().delete()
        org = self._get_org()
        org.config_settings.whois_enabled = True
        org.config_settings.save()

        with self.subTest("WHOIS lookup task called when last_ip is public"):
            with mock.patch(
                "django.core.cache.cache.get", return_value=None
            ) as mocked_get, mock.patch("django.core.cache.cache.set") as mocked_set:
                device = self._create_device(last_ip="172.217.22.14")
                mocked_lookup_task.assert_called()
                mocked_set.assert_called_once_with(
                    f"organization_config_{org.pk}",
                    org.config_settings,
                    timeout=Config._CHECKSUM_CACHE_TIMEOUT,
                )
                mocked_get.assert_called()
        mocked_lookup_task.reset_mock()

        with self.subTest(
            "WHOIS lookup task called when last_ip is changed and is public"
        ):
            with mock.patch("django.core.cache.cache.get") as mocked_get, mock.patch(
                "django.core.cache.cache.set"
            ) as mocked_set:
                device.last_ip = "172.217.22.10"
                device.save()
                device.refresh_from_db()
                mocked_lookup_task.assert_called()
                mocked_set.assert_not_called()
                mocked_get.assert_called()
        mocked_lookup_task.reset_mock()

        with self.subTest(
            "WHOIS lookup task not called when last_ip has related WhoIsInfo"
        ):
            device.last_ip = "172.217.22.14"
            self._create_whois_info(ip_address=device.last_ip)
            device.save()
            device.refresh_from_db()
            device.organization.config_settings.refresh_from_db()
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
            device1.refresh_from_db()
            mocked_task.assert_called()
            mocked_task.reset_mock()
            device2.last_ip = "172.217.22.13"
            device2.save()
            device2.refresh_from_db()
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
            mock_response = self._mocked_client_response()
            self.assertEqual(
                instance.isp, mock_response.traits.autonomous_system_organization
            )
            self.assertEqual(
                instance.asn, str(mock_response.traits.autonomous_system_number)
            )
            self.assertEqual(instance.timezone, mock_response.location.time_zone)
            mock_address = {
                "city": mock_response.city.name,
                "country": mock_response.country.name,
                "continent": mock_response.continent.name,
                "postal": mock_response.postal.code,
            }
            self.assertEqual(instance.address, mock_address)
            self.assertEqual(instance.cidr, "172.217.22.0/24")
            self.assertEqual(instance.ip_address, ip_address)
            formatted_address = WHOISInfo(address=mock_address).formatted_address
            self.assertEqual(instance.formatted_address, formatted_address)
            self.assertEqual(instance.coordinates.x, mock_response.location.longitude)
            self.assertEqual(instance.coordinates.y, mock_response.location.latitude)

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
            device.refresh_from_db()
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
            device.refresh_from_db()
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

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_whois_update(self, mock_client):
        connect_whois_handlers()
        mocked_response = self._mocked_client_response()
        mock_client.return_value.city.return_value = mocked_response
        threshold = app_settings.WHOIS_REFRESH_THRESHOLD_DAYS + 1
        new_time = timezone.now() - timedelta(days=threshold)
        whois_obj = self._create_whois_info()
        WHOISInfo.objects.filter(pk=whois_obj.pk).update(modified=new_time)

        with self.subTest("Test WHOIS update when older than X days for new device"):
            mocked_response.traits.autonomous_system_number = 11111
            mock_client.return_value.city.return_value = mocked_response
            device = self._create_device(last_ip=whois_obj.ip_address)
            whois_obj = device.whois_service.get_device_whois_info()
            self.assertEqual(whois_obj.asn, str(11111))

        with self.subTest(
            "Test WHOIS update not running for invalid ip address "
            "even if older than X days"
        ):
            Device.objects.all().delete()
            WHOISInfo.objects.all().delete()
            # to check ip address fallbacks are working if device created by
            # bypassing validations
            device = Device.objects.create(
                name="default.test.device",
                organization=self._get_org(),
                mac_address=self.TEST_MAC_ADDRESS,
                last_ip="InvalidIP",
            )
            whois_obj = device.whois_service.get_device_whois_info()
            self.assertEqual(whois_obj, None)
            device.save()
            device.refresh_from_db()
            whois_obj = device.whois_service.get_device_whois_info()
            self.assertEqual(whois_obj, None)

        with self.subTest(
            "Test WHOIS update not running if whois disabled even if older than X days"
        ):
            Device.objects.all().delete()
            WHOISInfo.objects.all().delete()
            device = self._create_device(last_ip="172.217.22.11")
            whois_obj = device.whois_service.get_device_whois_info()
            self.assertEqual(whois_obj.asn, str(11111))
            WHOISInfo.objects.filter(pk=whois_obj.pk).update(modified=new_time)
            mocked_response.traits.autonomous_system_number = 22222
            mock_client.return_value.city.return_value = mocked_response
            org = self._get_org()
            org.config_settings.whois_enabled = False
            org.config_settings.save()
            device.save()
            device.refresh_from_db()
            whois_obj = device.whois_service.get_device_whois_info()
            self.assertEqual(whois_obj, None)

        with self.subTest(
            "Test WHOIS update when older than X days for existing device"
        ):
            Device.objects.all().delete()
            WHOISInfo.objects.all().delete()
            org = self._get_org()
            org.config_settings.whois_enabled = True
            org.config_settings.save()
            device = self._create_device(last_ip="172.217.22.11")
            whois_obj = device.whois_service.get_device_whois_info()
            self.assertEqual(whois_obj.asn, str(22222))
            WHOISInfo.objects.filter(pk=whois_obj.pk).update(modified=new_time)
            mocked_response.traits.autonomous_system_number = 33333
            mock_client.return_value.city.return_value = mocked_response
            device.save()
            device.refresh_from_db()
            whois_obj = device.whois_service.get_device_whois_info()
            self.assertEqual(whois_obj.asn, str(33333))

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    def test_device_last_ip_deferred_checks(self):
        whois_obj = self._create_whois_info()
        self._create_device(last_ip=whois_obj.ip_address)
        # Deferred fields remained deferred
        device = Device.objects.only("id", "created").first()
        with self.subTest("Test deferred fields remained deferred after last_ip check"):
            device._check_last_ip()
            self.assertTrue(device._is_deferred("last_ip"))

        with self.subTest(
            "Test update_whois does not run if last_ip is deferred"
        ), mock.patch(
            "openwisp_controller.config.whois.service.WHOISService.update_whois_info"
        ) as mock_update_whois:
            threshold = app_settings.WHOIS_REFRESH_THRESHOLD_DAYS + 1
            new_time = timezone.now() - timedelta(days=threshold)
            WHOISInfo.objects.filter(pk=whois_obj.pk).update(modified=new_time)
            device._check_last_ip()
            mock_update_whois.assert_not_called()
            mock_update_whois.reset_mock()

    def test_create_or_update_whois_updates_modified_unchanged_details(self):
        """
        Test that _create_or_update_whois updates the modified field
        even when the WHOIS details are unchanged.
        """
        whois_obj = self._create_whois_info(ip_address="172.217.22.50")
        device = self._create_device(last_ip=whois_obj.ip_address)
        old_modified = whois_obj.modified
        whois_details = {
            "isp": whois_obj.isp,
            "asn": whois_obj.asn,
            "timezone": whois_obj.timezone,
            "address": whois_obj.address,
            "cidr": whois_obj.cidr,
            "coordinates": whois_obj.coordinates,
        }
        updated_obj, _ = device.whois_service._create_or_update_whois(
            whois_details, whois_obj
        )
        updated_obj.refresh_from_db()
        self.assertGreater(
            updated_obj.modified,
            old_modified,
        )

    # we need to allow the task to propagate exceptions to ensure
    # `on_failure` method is called and notifications are executed
    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_WHOIS_TASKS_ERR_LOGGER)
    @mock.patch(_WHOIS_TASKS_WARN_LOGGER)
    @mock.patch(_WHOIS_TASKS_INFO_LOGGER)
    def test_whois_task_failure_notification(self, mock_info, mock_warn, mock_error):
        def assert_logging_on_exception(
            exception, info_calls=0, warn_calls=0, error_calls=1, notification_count=1
        ):
            with self.subTest(
                f"Test notification and logging when {exception.__name__} is raised"
            ), mock.patch(self._WHOIS_GEOIP_CLIENT) as mock_client:
                mock_client.return_value.city.side_effect = exception("test")
                Device.objects.all().delete()  # Clear existing devices
                device = self._create_device(last_ip="172.217.22.14")
                self.assertEqual(mock_info.call_count, info_calls)
                self.assertEqual(mock_warn.call_count, warn_calls)
                self.assertEqual(mock_error.call_count, error_calls)
                if notification_count > 0:
                    notification_qs = _notification_qs()
                    self.assertEqual(notification_qs.count(), notification_count)
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
            _notification_qs().delete()

        # Test for all possible exceptions that can be raised by the geoip2 client
        # Notification are sent only one time when any of the following exceptions
        # are raised first time.
        assert_logging_on_exception(errors.OutOfQueriesError)
        assert_logging_on_exception(errors.AddressNotFoundError, notification_count=0)
        assert_logging_on_exception(errors.AuthenticationError, notification_count=0)
        assert_logging_on_exception(
            errors.PermissionRequiredError, notification_count=0
        )
        assert_logging_on_exception(RequestException, notification_count=0)
        cache.clear()

    @override_settings(CACHES=MODIFIED_CACHE)
    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    def test_whois_task_failure_cache(self):
        permanent_errors = [
            errors.AddressNotFoundError,
            errors.OutOfQueriesError,
            errors.AuthenticationError,
            errors.PermissionRequiredError,
        ]

        def trigger_error_and_assert_cached(exc, notification_count=0):
            with mock.patch(self._WHOIS_GEOIP_CLIENT) as mock_client:
                mock_client.return_value.city.side_effect = exc("test")
                Device.objects.all().delete()
                device = self._create_device(last_ip="172.217.22.14")
                cache_key = f"{self._WHOIS_TASK_NAME}_last_operation"
                self.assertEqual(cache.get(cache_key), "errored")
                self.assertEqual(_notification_qs().count(), notification_count)
                _notification_qs().delete()
                return device

        # simulate that no matter which permanent error is raised first,
        # the rest of the permanent errors should use the cache
        for first_error in permanent_errors:
            with self.subTest(f"Cache populated by {first_error.__name__}"):
                cache.clear()
                trigger_error_and_assert_cached(first_error, 1)
            for subsequent_error in permanent_errors:
                if subsequent_error is first_error:
                    continue
                with self.subTest(
                    f"Cache reused when {subsequent_error.__name__} occurs "
                    f"after {first_error.__name__}"
                ):
                    trigger_error_and_assert_cached(subsequent_error, 0)

        with self.subTest("Test cache updated on success"), mock.patch(
            self._WHOIS_GEOIP_CLIENT
        ) as mock_client:
            Device.objects.all().delete()
            mocked_response = self._mocked_client_response()
            mocked_response.location = None
            mock_client.return_value.city.return_value = mocked_response
            self._create_device(last_ip="172.217.22.14")
            cache_key = f"{self._WHOIS_TASK_NAME}_last_operation"
            self.assertEqual(cache.get(cache_key), "success")
            self.assertEqual(_notification_qs().count(), 0)
        cache.clear()

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=True)
    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch("openwisp_controller.config.whois.tasks.fetch_whois_details.retry")
    def test_whois_task_retry_mechanism(self, mock_retry):
        def assert_retry_on_exception(exception, should_retry):
            with self.subTest(
                f"Test retry mechanism when {exception.__name__} is raised"
            ), mock.patch(self._WHOIS_GEOIP_CLIENT) as mock_client:
                mock_client.return_value.city.side_effect = exception("test")
                Device.objects.all().delete()
                mock_retry.reset_mock()
                mock_retry.side_effect = exception("test")
                with self.assertRaises(exception):
                    self._create_device(last_ip="172.217.22.14")
                if should_retry:
                    self.assertEqual(mock_retry.call_count, 1)
                    assert isinstance(mock_retry.call_args.kwargs["exc"], exception)
                else:
                    self.assertEqual(mock_retry.call_count, 0)

        assert_retry_on_exception(errors.HTTPError, should_retry=True)
        assert_retry_on_exception(errors.OutOfQueriesError, should_retry=False)
        assert_retry_on_exception(errors.AddressNotFoundError, should_retry=False)
        assert_retry_on_exception(errors.AuthenticationError, should_retry=False)
        assert_retry_on_exception(errors.PermissionRequiredError, should_retry=False)

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_WHOIS_TASKS_WARN_LOGGER)
    def test_fetch_whois_details_device_not_found(self, mock_warn):
        invalid_pk = uuid4()
        fetch_whois_details(device_pk=invalid_pk, initial_ip_address="10.0.0.1")
        mock_warn.assert_called_once_with(
            f"Device {invalid_pk} not found, skipping WHOIS lookup"
        )

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_fetch_whois_details_record_already_exists(self, mock_client):
        whois_obj = self._create_whois_info()
        device = self._create_device(last_ip=whois_obj.ip_address)
        mock_client.return_value.city.return_value = self._mocked_client_response()
        fetch_whois_details(device_pk=device.pk, initial_ip_address="10.0.0.1")
        mock_client.assert_not_called()

    def test_send_whois_task_notification_with_invalid_device_pk(self):
        invalid_pk = uuid4()
        result = send_whois_task_notification(
            device=invalid_pk, notify_type="whois_device_error"
        )
        self.assertIsNone(result)

    def test_delete_whois_record_force(self):
        whois_obj = self._create_whois_info()
        ip_address = whois_obj.ip_address
        delete_whois_record(ip_address=ip_address, force=True)
        self.assertFalse(WHOISInfo.objects.filter(ip_address=ip_address).exists())

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    def test_get_whois_info_device_whois_disabled(self):
        org = self._get_org()
        org.config_settings.whois_enabled = False
        org.config_settings.save()
        device = self._create_device(last_ip="172.217.22.14")
        result = get_whois_info(pk=device.pk)
        self.assertIsNone(result)

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    def test_get_whois_info_with_none_pk(self):
        result = get_whois_info(pk=None)
        self.assertIsNone(result)

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    def test_get_whois_info_device_not_found(self):
        result = get_whois_info(pk=uuid4())
        self.assertIsNone(result)

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_get_whois_info_not_found(self, mock_client):
        mock_client.return_value.city.return_value = self._mocked_client_response()
        org = self._get_org()
        org.config_settings.whois_enabled = True
        org.config_settings.save()
        device = self._create_device(last_ip="172.217.22.14")
        WHOISInfo.objects.all().delete()
        result = get_whois_info(pk=device.pk)
        self.assertIsNone(result)

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_get_whois_info_returns_data_with_formatted_address(self, mock_client):
        mock_client.return_value.city.return_value = self._mocked_client_response()
        org = self._get_org()
        device = self._create_device(last_ip="172.217.22.14")
        WHOISInfo.objects.filter(ip_address=device.last_ip).delete()
        org.config_settings.whois_enabled = True
        org.config_settings.save()
        WHOISInfo.objects.create(
            ip_address=device.last_ip,
            address={
                "city": "Mountain View",
                "country": "United States",
                "postal": "94043",
            },
        )
        result = get_whois_info(pk=device.pk)
        self.assertIsNotNone(result)
        self.assertEqual(
            result["formatted_address"], "Mountain View, United States, 94043"
        )

    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", False)
    def test_get_whois_info_when_not_configured(self):
        device = self._create_device(last_ip="172.217.22.14")
        result = get_whois_info(pk=device.pk)
        self.assertIsNone(result)


@tag("selenium_tests")
class TestWHOISSelenium(CreateWHOISMixin, SeleniumTestMixin, StaticLiveServerTestCase):
    @mock.patch.object(app_settings, "WHOIS_CONFIGURED", True)
    def test_whois_device_admin(self):
        def _assert_no_js_errors():
            browser_logs = []
            for log in self.get_browser_logs():
                if self.browser == "chrome" and log["source"] != "console-api":
                    continue
                elif log["message"] in ["wrong event specified: touchleave"]:
                    continue
                browser_logs.append(log)
            self.assertEqual(browser_logs, [])

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
            _assert_no_js_errors()

        with mock.patch.object(app_settings, "WHOIS_CONFIGURED", False):
            with self.subTest(
                "WHOIS details not visible in device admin "
                + "when WHOIS_CONFIGURED is False"
            ):
                self.open(reverse("admin:config_device_change", args=[device.pk]))
                self.wait_for_invisibility(By.CSS_SELECTOR, "table.whois-table")
                self.wait_for_invisibility(By.CSS_SELECTOR, "details.whois")
                _assert_no_js_errors()

        with self.subTest(
            "WHOIS details not visible in device admin when WHOIS is disabled"
        ):
            org = self._get_org()
            org.config_settings.whois_enabled = False
            org.config_settings.save(update_fields=["whois_enabled"])
            org.config_settings.refresh_from_db(fields=["whois_enabled"])
            self.open(reverse("admin:config_device_change", args=[device.pk]))
            self.wait_for_invisibility(By.CSS_SELECTOR, "table.whois-table")
            self.wait_for_invisibility(By.CSS_SELECTOR, "details.whois")
            _assert_no_js_errors()

        with self.subTest(
            "WHOIS details not visible in device admin when WHOIS Info does not exist"
        ):
            org = self._get_org()
            org.config_settings.whois_enabled = True
            org.config_settings.save(update_fields=["whois_enabled"])
            org.config_settings.refresh_from_db(fields=["whois_enabled"])
            WHOISInfo.objects.all().delete()
            self.open(reverse("admin:config_device_change", args=[device.pk]))
            self.wait_for_invisibility(By.CSS_SELECTOR, "table.whois-table")
            self.wait_for_invisibility(By.CSS_SELECTOR, "details.whois")
            _assert_no_js_errors()

        with self.subTest("Check XSS protection in WHOIS details admin view"):
            whois_data = {
                "ip_address": device.last_ip,
                "isp": "<img src=x onerror=alert('XSS')>",
                "timezone": "<script>alert('XSS')</script>",
                "address": {
                    "city": "Mountain View",
                    "country": "<script>alert('XSS')</script>",
                    "continent": "North America",
                    "postal": "94043",
                },
            }
            WHOISInfo.objects.all().delete()
            self._create_whois_info(**whois_data)
            try:
                self.open(reverse("admin:config_device_change", args=[device.pk]))
                table = self.find_element(By.CSS_SELECTOR, "table.whois-table")
                rows = table.find_elements(By.TAG_NAME, "tr")
                for row in rows:
                    if cells := row.find_elements(By.TAG_NAME, "td"):
                        self.assertIn("onerror", cells[0].text)
                        self.assertIn("script", cells[1].text)
                details = self.find_element(By.CSS_SELECTOR, "details.whois")
                self.web_driver.execute_script(
                    "arguments[0].setAttribute('open','')", details
                )
                additional_text = details.find_elements(
                    By.CSS_SELECTOR, ".additional-text"
                )
                self.assertIn("script", additional_text[1].text)
                self.assertIn("script", additional_text[2].text)
                _assert_no_js_errors()
            except UnexpectedAlertPresentException:
                self.fail("XSS vulnerability detected in WHOIS details admin view.")
