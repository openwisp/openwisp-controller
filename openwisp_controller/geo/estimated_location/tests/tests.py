import contextlib
import importlib
from datetime import timedelta
from unittest import mock
from uuid import uuid4

from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openwisp_notifications.types import unregister_notification_type
from swapper import load_model

from openwisp_controller.config import settings as config_app_settings
from openwisp_controller.config.whois.handlers import connect_whois_handlers
from openwisp_controller.config.whois.tests.utils import WHOISTransactionMixin
from openwisp_controller.geo import estimated_location

from ....tests.utils import TestAdminMixin
from ...tests.utils import TestGeoMixin
from ..handlers import register_estimated_location_notification_types
from ..tasks import manage_estimated_locations
from .utils import TestEstimatedLocationMixin

Config = load_model("config", "Config")
Device = load_model("config", "Device")
Location = load_model("geo", "Location")
DeviceLocation = load_model("geo", "DeviceLocation")
WHOISInfo = load_model("config", "WHOISInfo")
Notification = load_model("openwisp_notifications", "Notification")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")


def _notification_qs():
    return Notification.objects.all()


class TestEstimatedLocation(TestAdminMixin, TestCase):
    @override_settings(
        OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT="test_account",
        OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY="test_key",
    )
    def test_estimated_location_configuration_setting(self):
        # reload app_settings to apply the overridden
        self.addCleanup(importlib.reload, config_app_settings)
        importlib.reload(config_app_settings)
        with self.subTest(
            "ImproperlyConfigured raised when ESTIMATED_LOCATION_ENABLED is True "
            "and WHOIS_ENABLED is False globally"
        ):
            with override_settings(
                OPENWISP_CONTROLLER_WHOIS_ENABLED=False,
                OPENWISP_CONTROLLER_ESTIMATED_LOCATION_ENABLED=True,
            ):
                with self.assertRaises(ImproperlyConfigured):
                    # reload app_settings to apply the overridden settings
                    importlib.reload(config_app_settings)

        with self.subTest(
            "Test WHOIS not enabled does not allow enabling Estimated Location"
        ):
            org_settings_obj = OrganizationConfigSettings(organization=self._get_org())
            with self.assertRaises(ValidationError) as context_manager:
                org_settings_obj.whois_enabled = False
                org_settings_obj.estimated_location_enabled = True
                org_settings_obj.full_clean()
            self.assertEqual(
                context_manager.exception.message_dict["estimated_location_enabled"][0],
                "Estimated Location feature requires "
                + "WHOIS Lookup feature to be enabled.",
            )

        with self.subTest(
            "Test Estimated Location field visible on admin when "
            "WHOIS_CONFIGURED is True"
        ):
            self._login()
            org = self._get_org()
            url = reverse(
                "admin:openwisp_users_organization_change",
                args=[org.pk],
            )
            response = self.client.get(url)
            self.assertContains(
                response, 'name="config_settings-0-estimated_location_enabled"'
            )

        with override_settings(
            OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT=None,
            OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY=None,
        ):
            importlib.reload(config_app_settings)
            with self.subTest(
                "Test Estimated Location field hidden on admin when "
                "WHOIS_CONFIGURED is False"
            ):
                self._login()
                org = self._get_org()
                url = reverse(
                    "admin:openwisp_users_organization_change",
                    args=[org.pk],
                )
                response = self.client.get(url)
                self.assertNotContains(
                    response, 'name="config_settings-0-estimated_location_enabled"'
                )


class TestEstimatedLocationField(TestEstimatedLocationMixin, TestGeoMixin, TestCase):
    location_model = Location

    def test_estimated_location_field(self):
        org = self._get_org()
        org.config_settings.estimated_location_enabled = False
        org.config_settings.save()
        org.refresh_from_db()
        with self.assertRaises(ValidationError) as context_manager:
            self._create_location(organization=org, is_estimated=True)
        self.assertEqual(
            context_manager.exception.message_dict["is_estimated"][0],
            "Estimated Location feature required to be configured.",
        )

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    def test_estimated_location_admin(self):
        connect_whois_handlers()
        admin = self._create_admin()
        self.client.force_login(admin)
        org = self._get_org()
        location = self._create_location(organization=org, is_estimated=True)
        change_path = reverse("admin:geo_location_change", args=[location.pk])
        add_path = reverse("admin:geo_location_add")

        with self.subTest(
            "is-estimated field visible when estimated location is enabled"
        ):
            response = self.client.get(change_path)
            self.assertContains(response, "field-is_estimated")
            self.assertContains(
                response, "Whether the location's coordinates are estimated."
            )
        with self.subTest(
            "is-estimated field not visible in add pages because auto-managed"
        ):
            response = self.client.get(add_path)
            self.assertNotContains(response, "field-is_estimated")

        org.config_settings.estimated_location_enabled = False
        org.config_settings.save()
        org.config_settings.refresh_from_db()

        with self.subTest(
            "is-estimated field hidden when estimated location is disabled"
        ):
            response = self.client.get(change_path)
            self.assertNotContains(response, "field-is_estimated")
            self.assertNotContains(
                response, "Whether the location's coordinates are estimated."
            )
        with self.subTest(
            "double-check is-estimated field is not "
            "leaking if estimated location is disabled"
        ):
            response = self.client.get(add_path)
            self.assertNotContains(response, "field-is_estimated")

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", False)
    def test_estimated_location_admin_add_whois_disabled(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        path = reverse("admin:geo_location_add")
        response = self.client.get(path)
        self.assertNotContains(response, "field-is_estimated")


class TestEstimatedLocationTransaction(
    TestEstimatedLocationMixin, WHOISTransactionMixin, TestGeoMixin, TransactionTestCase
):
    location_model = Location
    object_location_model = DeviceLocation

    _WHOIS_GEOIP_CLIENT = (
        "openwisp_controller.config.whois.service.geoip2_webservice.Client"
    )
    _ESTIMATED_LOCATION_INFO_LOGGER = (
        "openwisp_controller.geo.estimated_location.tasks.logger.info"
    )
    _ESTIMATED_LOCATION_WARNING_LOGGER = (
        "openwisp_controller.geo.estimated_location.tasks.logger.warning"
    )
    _ESTIMATED_LOCATION_ERROR_LOGGER = (
        "openwisp_controller.geo.estimated_location.tasks.logger.error"
    )
    _WHOIS_TASK_NAME = "openwisp_controller.config.whois.tasks.fetch_whois_details"

    def setUp(self):
        super().setUp()
        self.admin = self._get_admin()
        # Unregister the notification type if it was previously registered
        with contextlib.suppress(ImproperlyConfigured):
            unregister_notification_type("estimated_location_info")
        with mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True):
            register_estimated_location_notification_types()

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(
        "openwisp_controller.config.whois.service.WHOISService.trigger_estimated_location_task"  # noqa: E501
    )
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_estimated_location_task_called(
        self, mocked_client, mocked_estimated_location_task
    ):
        connect_whois_handlers()
        mocked_response = self._mocked_client_response()
        mocked_client.return_value.city.return_value = mocked_response
        threshold = config_app_settings.WHOIS_REFRESH_THRESHOLD_DAYS + 1

        self._task_called(
            mocked_estimated_location_task, task_name="Estimated location"
        )

        Device.objects.all().delete()
        WHOISInfo.objects.all().delete()
        org = self._get_org()
        org.config_settings.whois_enabled = True
        org.config_settings.estimated_location_enabled = True
        org.config_settings.save()

        with self.subTest("Estimated location task called when last_ip is public"):
            with mock.patch(
                "django.core.cache.cache.get", return_value=None
            ) as mocked_get, mock.patch("django.core.cache.cache.set") as mocked_set:
                device = self._create_device(last_ip="172.217.22.14")
                mocked_estimated_location_task.assert_called()
                expected_cache_set_calls = [
                    mock.call(
                        f"organization_config_{org.pk}",
                        org.config_settings,
                        timeout=Config._CHECKSUM_CACHE_TIMEOUT,
                    ),
                    mock.call(
                        f"{self._WHOIS_TASK_NAME}_last_operation", "success", None
                    ),
                ]
                mocked_set.assert_has_calls(expected_cache_set_calls)
                mocked_get.assert_called()
        mocked_estimated_location_task.reset_mock()

        with self.subTest(
            "Estimated location task called when last_ip is changed and is public"
        ):
            with mock.patch("django.core.cache.cache.get") as mocked_get, mock.patch(
                "django.core.cache.cache.set"
            ) as mocked_set:
                device.last_ip = "172.217.22.10"
                device.save()
                device.refresh_from_db()
                mocked_estimated_location_task.assert_called()
                expected_cache_set_calls = [
                    mock.call(
                        f"{self._WHOIS_TASK_NAME}_last_operation", "success", None
                    ),
                ]
                mocked_set.assert_has_calls(expected_cache_set_calls)
                mocked_get.assert_called()
        mocked_estimated_location_task.reset_mock()

        with self.subTest(
            "Estimated location task called when last_ip has related WhoIsInfo"
        ):
            with mock.patch("django.core.cache.cache.get") as mocked_get, mock.patch(
                "django.core.cache.cache.set"
            ) as mocked_set:
                self._create_config(device=device)
                device.last_ip = "172.217.22.14"
                self._create_whois_info(ip_address=device.last_ip)
                device.save()
                device.refresh_from_db()
                device.organization.config_settings.refresh_from_db()
                mocked_set.assert_not_called()
                # The cache `get` is called twice, once for `whois_enabled` and
                # once for `estimated_location_enabled`
                mocked_get.assert_called()
                mocked_estimated_location_task.assert_called()
        mocked_estimated_location_task.reset_mock()

        with self.subTest(
            "Estimated location task not called via DeviceChecksumView when "
            "last_ip already has related WhoIsInfo"
        ):
            WHOISInfo.objects.all().delete()
            self._create_whois_info(ip_address=device.last_ip)
            response = self.client.get(
                reverse("controller:device_checksum", args=[device.pk]),
                {"key": device.key},
                REMOTE_ADDR=device.last_ip,
            )
            self.assertEqual(response.status_code, 200)
            mocked_estimated_location_task.assert_not_called()
        mocked_estimated_location_task.reset_mock()

        with self.subTest(
            "Estimate location task not called when address/coordinates not updated"
        ):
            WHOISInfo.objects.all().delete()
            whois_obj = self._create_whois_info(ip_address=device.last_ip)
            WHOISInfo.objects.filter(pk=whois_obj.pk).update(
                modified=timezone.now() - timedelta(days=threshold)
            )
            self._create_object_location(content_object=device)
            device.save()
            device.refresh_from_db()
            mocked_estimated_location_task.assert_not_called()
            mocked_estimated_location_task.reset_mock()
            response = self.client.get(
                reverse("controller:device_checksum", args=[device.pk]),
                {"key": device.key},
                REMOTE_ADDR=device.last_ip,
            )
            self.assertEqual(response.status_code, 200)
            mocked_estimated_location_task.assert_not_called()
        mocked_estimated_location_task.reset_mock()

        with self.subTest(
            "Estimate location task called when address/coordinates updated"
        ):
            WHOISInfo.objects.all().delete()
            whois_obj = self._create_whois_info(ip_address=device.last_ip)
            WHOISInfo.objects.filter(pk=whois_obj.pk).update(
                modified=timezone.now() - timedelta(days=threshold)
            )
            mocked_response.city.name = "New city"
            mocked_client.return_value.city.return_value = mocked_response
            device.save()
            device.refresh_from_db()
            mocked_estimated_location_task.assert_called()
        mocked_estimated_location_task.reset_mock()

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch("openwisp_controller.config.whois.service.send_whois_task_notification")
    @mock.patch(
        "openwisp_controller.geo.estimated_location.tasks.send_whois_task_notification"
    )
    @mock.patch(
        "openwisp_controller.config.whois.service.WHOISService.trigger_estimated_location_task"  # noqa: E501
    )
    @mock.patch(_ESTIMATED_LOCATION_INFO_LOGGER)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_estimated_location_creation_and_update(
        self, mock_client, mock_info, _mocked_task, _mocked_notify, _mocked_notify2
    ):
        connect_whois_handlers()

        def _verify_location_details(device, mocked_response):
            location = device.devicelocation.location
            mocked_location = mocked_response.location
            mock_address = {
                "city": mocked_response.city.name,
                "country": mocked_response.country.name,
                "continent": mocked_response.continent.name,
                "postal": mocked_response.postal.code,
            }
            address = WHOISInfo(address=mock_address).formatted_address
            ip_address = mocked_response.ip_address or device.last_ip
            location_name = WHOISInfo(
                address=mock_address, ip_address=ip_address
            )._location_name
            self.assertEqual(location.name, location_name)
            self.assertEqual(location.address, address)
            self.assertEqual(
                location.geometry,
                GEOSGeometry(
                    f"POINT({mocked_location.longitude} {mocked_location.latitude})",
                    srid=4326,
                ),
            )

        mocked_response = self._mocked_client_response()
        mock_client.return_value.city.return_value = mocked_response

        with self.subTest("Test Estimated location created when device is created"):
            device = self._create_device(last_ip="172.217.22.14")
            with self.assertNumQueries(13):
                manage_estimated_locations(device.pk, device.last_ip)
            location = device.devicelocation.location
            mocked_response.ip_address = device.last_ip
            self.assertEqual(location.is_estimated, True)
            self.assertEqual(location.is_mobile, False)
            self.assertEqual(location.type, "outdoor")
            _verify_location_details(device, mocked_response)
            mock_info.assert_called_once_with(
                f"Estimated location saved successfully for {device.pk}"
                f" for IP: {device.last_ip}"
            )
        mock_info.reset_mock()

        with self.subTest("Test Estimated location updated when last ip is updated"):
            device.last_ip = "172.217.22.10"
            mocked_response.location.latitude = 50
            mocked_response.location.longitude = 150
            mocked_response.city.name = "New City"
            mock_client.return_value.city.return_value = mocked_response
            device.save()
            device.refresh_from_db()
            with self.assertNumQueries(7):
                manage_estimated_locations(device.pk, device.last_ip)

            location = device.devicelocation.location
            mocked_response.ip_address = device.last_ip
            self.assertEqual(location.is_estimated, True)
            self.assertEqual(location.is_mobile, False)
            self.assertEqual(location.type, "outdoor")
            _verify_location_details(device, mocked_response)
            mock_info.assert_called_once_with(
                f"Estimated location saved successfully for {device.pk}"
                f" for IP: {device.last_ip}"
            )
        mock_info.reset_mock()

        with self.subTest("Test Estimated location Name when address not available"):
            device.last_ip = "172.217.22.11"
            mocked_response.city.name = ""
            mocked_response.country.name = ""
            mocked_response.continent.name = ""
            mocked_response.postal.code = ""
            mock_client.return_value.city.return_value = mocked_response
            device.save()
            device.refresh_from_db()
            with self.assertNumQueries(7):
                manage_estimated_locations(device.pk, device.last_ip)

            location = device.devicelocation.location
            mocked_response.ip_address = device.last_ip
            self.assertEqual(location.is_estimated, True)
            self.assertEqual(location.is_mobile, False)
            _verify_location_details(device, mocked_response)
            mock_info.assert_called_once_with(
                f"Estimated location saved successfully for {device.pk}"
                f" for IP: {device.last_ip}"
            )
        mock_info.reset_mock()

        with self.subTest(
            "Test Non Estimated Location not updated when last ip is updated"
        ):
            mocked_response.ip_address = device.last_ip
            device.last_ip = "172.217.22.12"
            device.devicelocation.location.is_estimated = False
            mock_client.return_value.city.return_value = self._mocked_client_response()
            device.devicelocation.location.save(_set_estimated=True)
            device.save()
            device.refresh_from_db()
            with self.assertNumQueries(2):
                manage_estimated_locations(device.pk, device.last_ip)

            location = device.devicelocation.location
            self.assertEqual(location.is_estimated, False)
            self.assertEqual(location.is_mobile, False)
            self.assertEqual(location.type, "outdoor")
            _verify_location_details(device, mocked_response)
            mock_info.assert_called_once_with(
                f"Non Estimated location already set for {device.pk}. Update"
                f" location manually as per IP: {device.last_ip}"
            )
        mock_info.reset_mock()

        with self.subTest(
            "Test location shared for same IP when new device's location does not exist"
        ):
            Device.objects.all().delete()
            device1 = self._create_device(last_ip="172.217.22.10")
            manage_estimated_locations(device1.pk, device1.last_ip)
            mock_info.reset_mock()
            device2 = self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.10",
            )
            with self.assertNumQueries(7):
                manage_estimated_locations(device2.pk, device2.last_ip)

            self.assertEqual(
                device1.devicelocation.location.pk, device2.devicelocation.location.pk
            )
            mock_info.assert_called_once_with(
                f"Estimated location saved successfully for {device2.pk}"
                f" for IP: {device2.last_ip}"
            )
        mock_info.reset_mock()

        with self.subTest(
            "Test location shared for same IP when new device's location is estimated"
        ):
            Device.objects.all().delete()
            device1 = self._create_device(last_ip="172.217.22.10")
            manage_estimated_locations(device1.pk, device1.last_ip)
            device2 = self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.11",
            )
            manage_estimated_locations(device2.pk, device2.last_ip)
            mock_info.reset_mock()
            old_location = device2.devicelocation.location
            device2.last_ip = "172.217.22.10"
            device2.save()
            # 3 queries related to notifications cleanup
            device2.refresh_from_db()
            with self.assertNumQueries(15):
                manage_estimated_locations(device2.pk, device2.last_ip)
            mock_info.assert_called_once_with(
                f"Estimated location saved successfully for {device2.pk}"
                f" for IP: {device2.last_ip}"
            )

            self.assertEqual(
                device1.devicelocation.location.pk, device2.devicelocation.location.pk
            )
            self.assertEqual(Location.objects.filter(pk=old_location.pk).count(), 0)
        mock_info.reset_mock()

        with self.subTest(
            "Test location not shared for same IP when new "
            "device's location is not estimated"
        ):
            Device.objects.all().delete()
            device1 = self._create_device(last_ip="172.217.22.10")
            manage_estimated_locations(device1.pk, device1.last_ip)
            device2 = self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.11",
            )
            manage_estimated_locations(device2.pk, device2.last_ip)
            mock_info.reset_mock()
            old_location = device2.devicelocation.location
            old_location.is_estimated = False
            old_location.save()
            device2.last_ip = "172.217.22.10"
            device2.save()
            device2.refresh_from_db()
            with self.assertNumQueries(2):
                manage_estimated_locations(device2.pk, device2.last_ip)
            mock_info.assert_called_once_with(
                f"Non Estimated location already set for {device2.pk}. Update"
                f" location manually as per IP: {device2.last_ip}"
            )

            self.assertNotEqual(
                device1.devicelocation.location.pk, device2.devicelocation.location.pk
            )
            self.assertEqual(Location.objects.filter(pk=old_location.pk).count(), 1)
        mock_info.reset_mock()

        with self.subTest(
            "Shared location not updated when either device's last_ip changes. "
            "New location created for device with updated last_ip"
        ):
            Device.objects.all().delete()
            device1 = self._create_device(last_ip="172.217.22.10")
            manage_estimated_locations(device1.pk, device1.last_ip)
            device2 = self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.10",
            )
            manage_estimated_locations(device2.pk, device2.last_ip)
            mock_info.reset_mock()
            self.assertEqual(
                device1.devicelocation.location.pk, device2.devicelocation.location.pk
            )
            device2.last_ip = "172.217.22.11"
            device2.save()
            device2.refresh_from_db()
            with self.assertNumQueries(13):
                manage_estimated_locations(device2.pk, device2.last_ip)
            mock_info.assert_called_once_with(
                f"Estimated location saved successfully for {device2.pk}"
                f" for IP: {device2.last_ip}"
            )
            self.assertNotEqual(
                device1.devicelocation.location.pk, device2.devicelocation.location.pk
            )
        mock_info.reset_mock()

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_ESTIMATED_LOCATION_WARNING_LOGGER)
    def test_manage_estimated_location_device_not_found(self, mock_warn):
        invalid_pk = uuid4()
        manage_estimated_locations(device_pk=invalid_pk, ip_address="10.0.0.1")
        mock_warn.assert_called_once_with(
            f"Device {invalid_pk} not found, skipping manage_estimated_locations"
        )

    @mock.patch(
        "openwisp_controller.config.whois.service.current_app.send_task",
        side_effect=TestEstimatedLocationMixin.run_task,
    )
    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_estimated_location_handling_on_whois_update(
        self, mock_client, mock_send_task
    ):
        mocked_response = self._mocked_client_response()
        mock_client.return_value.city.return_value = mocked_response
        threshold = config_app_settings.WHOIS_REFRESH_THRESHOLD_DAYS + 1
        new_time = timezone.now() - timedelta(days=threshold)
        org = self._get_org()
        org.config_settings.estimated_location_enabled = False
        org.config_settings.save()
        device = self._create_device(last_ip="172.217.22.10")
        with self.assertRaises(Device.devicelocation.RelatedObjectDoesNotExist):
            # Accessing devicelocation to verify it doesn't exist (raises if not)
            device.devicelocation
        org.config_settings.estimated_location_enabled = True
        org.config_settings.save()
        whois_obj = device.whois_service.get_device_whois_info()
        WHOISInfo.objects.filter(pk=whois_obj.pk).update(modified=new_time)
        device.name = "test.new.name"
        device.save()
        device.refresh_from_db()
        # location created so can safely access devicelocation
        # Accessing devicelocation to verify it exists (raises if not)
        device.devicelocation

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(
        "openwisp_controller.config.whois.service.current_app.send_task",
        side_effect=TestEstimatedLocationMixin.run_task,
    )
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_unchanged_whois_data_no_location_recreation(self, mock_client, _):
        """Ensure identical WHOIS results do not recreate a shared Location when
        devices reuse the same IP."""
        connect_whois_handlers()
        mocked_response = self._mocked_client_response()
        mock_client.return_value.city.return_value = mocked_response
        shared_ip = "20.49.19.19"
        device1 = self._create_device(
            name="device-a",
            mac_address="00:11:22:33:44:55",
            last_ip=shared_ip,
        )
        device2 = self._create_device(
            name="device-b",
            mac_address="00:11:22:33:44:66",
            last_ip=shared_ip,
        )
        original_location = device1.devicelocation.location
        self.assertEqual(original_location.pk, device2.devicelocation.location.pk)
        location_count = Location.objects.count()
        notification_count = _notification_qs().count()
        # Clear the last ip for both devices, so setting them again
        # will trigger the WHOIS lookup flow.
        for device in (device1, device2):
            device.last_ip = ""
            device.save(update_fields=["last_ip"])
            device.refresh_from_db()
        # We set the same shared IP again. This simulates device fetching checksum.
        for device in (device1, device2):
            device.last_ip = shared_ip
            device.save(update_fields=["last_ip"])
            device.refresh_from_db()
        # The location object should remain unchanged since the WHOIS data is the same.
        self.assertEqual(original_location.pk, device1.devicelocation.location.pk)
        self.assertEqual(
            device1.devicelocation.location.pk, device2.devicelocation.location.pk
        )
        self.assertEqual(Location.objects.count(), location_count)
        self.assertTrue(Location.objects.filter(pk=original_location.pk).exists())
        self.assertEqual(_notification_qs().count(), notification_count)

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(
        "openwisp_controller.config.whois.service.current_app.send_task",
        side_effect=TestEstimatedLocationMixin.run_task,
    )
    @mock.patch(_ESTIMATED_LOCATION_INFO_LOGGER)
    @mock.patch(_ESTIMATED_LOCATION_ERROR_LOGGER)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_estimated_location_notification(
        self, mock_client, mock_error, mock_info, _
    ):
        def _verify_notification(device, messages, notify_level="info"):
            notification_qs = _notification_qs()
            self.assertEqual(notification_qs.count(), 1)
            notification = notification_qs.first()
            device_location = getattr(device, "devicelocation", None)
            actor = device
            if device_location:
                actor = device_location.location
            self.assertEqual(notification.actor, actor)
            self.assertEqual(notification.target, device)
            self.assertEqual(notification.type, "estimated_location_info")
            self.assertEqual(notification.level, notify_level)
            for message in messages:
                self.assertIn(message, notification.message)
            self.assertIn(device.last_ip, notification.rendered_description)
            self.assertIn("#devicelocation-group", notification.target_url)

        with self.subTest("Test Notification for location create"):
            mocked_response = self._mocked_client_response()
            mock_client.return_value.city.return_value = mocked_response
            device1 = self._create_device(last_ip="172.217.22.10")
            messages = ["Estimated location", "created successfully"]
            _verify_notification(device1, messages)

        with self.subTest("Test Notification for location update"):
            _notification_qs().delete()
            # will have same location as first device
            device2 = self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.10",
            )
            messages = ["Estimated location", "updated successfully"]
            _verify_notification(device2, messages)

        with self.subTest("Test Error Notification for conflicting locations"):
            _notification_qs().delete()
            mock_info.reset_mock()
            mock_error.reset_mock()
            device3 = self._create_device(
                name="11:22:33:44:55:77",
                mac_address="11:22:33:44:55:77",
                last_ip=device2.last_ip,
            )
            mock_info.assert_not_called()
            mock_error.assert_called_once_with(
                f"Multiple devices with locations found with same "
                f"last_ip {device3.last_ip}. Please resolve the conflict manually."
            )
            messages = [
                "Unable to create estimated location for device",
                "Please assign/create a location manually.",
            ]
            _verify_notification(device3, messages, "error")

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch("openwisp_controller.config.whois.service.send_whois_task_notification")
    @mock.patch(
        "openwisp_controller.geo.estimated_location.tasks.send_whois_task_notification"
    )
    @mock.patch(
        "openwisp_controller.config.whois.service.WHOISService.trigger_estimated_location_task"  # noqa: E501
    )
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_manage_estimated_locations_no_coordinates_warning(
        self, mock_client, _mocked_task, _mocked_notify, _mocked_notify2
    ):
        with mock.patch.object(estimated_location.tasks.logger, "warning") as mock_warn:
            connect_whois_handlers()
            mock_client.return_value.city.return_value = self._mocked_client_response()
            device = self._create_device(last_ip="172.217.22.14")
            WHOISInfo.objects.filter(ip_address=device.last_ip).delete()
            WHOISInfo.objects.create(
                ip_address=device.last_ip,
                address={
                    "city": "Mountain View",
                    "country": "United States",
                    "postal": "94043",
                },
            )
            manage_estimated_locations(device.pk, device.last_ip)
            mock_warn.assert_called_once_with(
                f"Coordinates not available for {device.pk} for IP: {device.last_ip}. "
                "Estimated location cannot be determined."
            )

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(
        "openwisp_controller.config.whois.service.current_app.send_task",
        side_effect=TestEstimatedLocationMixin.run_task,
    )
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_estimate_location_status_remove(self, mock_client, _):
        mocked_response = self._mocked_client_response()
        mock_client.return_value.city.return_value = mocked_response
        device = self._create_device(last_ip="172.217.22.10")
        location = device.devicelocation.location
        self.assertTrue(location.is_estimated)
        org = self._get_org()
        connect_whois_handlers()

        with self.subTest(
            "Test Estimated Status unchanged if Estimated feature is disabled"
        ):
            org.config_settings.estimated_location_enabled = False
            org.config_settings.save()
            org.config_settings.refresh_from_db()
            location.geometry = GEOSGeometry("POINT(12.512124 41.898903)", srid=4326)
            location.save()
            location.refresh_from_db()
            self.assertTrue(location.is_estimated)
            self.assertIn(f": {device.last_ip}", location.name)

        with self.subTest(
            "Test Estimated Status unchanged if Estimated feature is enabled"
            " and desired fields not changed"
        ):
            org.config_settings.estimated_location_enabled = True
            org.config_settings.save()
            org.config_settings.refresh_from_db()
            location._set_initial_values_for_changed_checked_fields()
            location.type = "outdoor"
            location.is_mobile = True
            location.save()
            location.refresh_from_db()
            self.assertTrue(location.is_estimated)

        with self.subTest(
            "Test Estimated Status changed if Estimated feature is enabled"
            " and desired fields changed"
        ):
            location.geometry = GEOSGeometry("POINT(15.512124 45.898903)", srid=4326)
            location.save(update_fields=["geometry"])
            location.refresh_from_db()
            self.assertFalse(location.is_estimated)
            # Note: Name is no longer automatically cleaned up when
            # is_estimated becomes False. Users must update the name manually
            # if desired


class TestEstimatedLocationFieldFilters(
    TestEstimatedLocationMixin, TestGeoMixin, TestCase
):
    location_model = Location
    object_location_model = DeviceLocation

    def setUp(self):
        super().setUp()
        admin = self._create_admin()
        self.client.force_login(admin)

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    def test_estimated_location_api_status_configured(self):
        org1 = self._get_org()
        org2 = self._create_org(name="org2")
        OrganizationConfigSettings.objects.create(
            organization=org2,
            whois_enabled=False,
            estimated_location_enabled=False,
        )
        org1_location = self._create_location(
            name="org1-location", organization=org1, is_estimated=True
        )
        org2_location = self._create_location(name="org2-location", organization=org2)
        org1_device = self._create_device(organization=org1)
        org2_device = self._create_device(organization=org2)
        self._create_object_location(content_object=org1_device, location=org1_location)
        self._create_object_location(content_object=org2_device, location=org2_location)

        with self.subTest("Test Estimated Location in Locations List"):
            path = reverse("geo_api:list_location")
            with self.assertNumQueries(4):
                response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 2)
            self.assertContains(response, org1_location.id)
            self.assertContains(response, org2_location.id)
            results_by_id = {item["id"]: item for item in response.data["results"]}
            self.assertIn("is_estimated", results_by_id[str(org1_location.id)])
            self.assertNotIn("is_estimated", results_by_id[str(org2_location.id)])

        with self.subTest("Test Estimated Location in Device Locations List"):
            path = reverse("geo_api:device_location", args=[org1_device.pk])
            with self.assertNumQueries(4):
                response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("is_estimated", response.data["location"]["properties"])
            path = reverse("geo_api:device_location", args=[org2_device.pk])
            with self.assertNumQueries(4):
                response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("is_estimated", response.data["location"]["properties"])

        with self.subTest("Test Estimated Location in GeoJSON List"):
            path = reverse("geo_api:location_geojson")
            with self.assertNumQueries(3):
                response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 2)
            results_by_id = {item["id"]: item for item in response.data["features"]}
            location1_result = results_by_id[str(org1_location.id)]
            location2_result = results_by_id[str(org2_location.id)]
            self.assertIn("is_estimated", location1_result["properties"])
            self.assertTrue(location1_result["properties"]["is_estimated"])
            self.assertNotIn("is_estimated", location2_result["properties"])

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", False)
    def test_estimated_location_api_status_not_configured(self):
        org = self._get_org()
        location = self._create_location(name="org1-location", organization=org)
        device = self._create_device(organization=org)
        self._create_object_location(content_object=device, location=location)

        with self.subTest("Test Estimated status not in Locations List"):
            path = reverse("geo_api:list_location")
            with self.assertNumQueries(4):
                response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 1)
            self.assertContains(response, location.id)
            api_location = response.data["results"][0]
            self.assertNotIn("is_estimated", api_location)

        with self.subTest("Test Estimated status not in Device Locations List"):
            path = reverse("geo_api:device_location", args=[device.pk])
            with self.assertNumQueries(4):
                response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("is_estimated", response.data["location"]["properties"])

        with self.subTest("Test Estimated status not in GeoJSON Location List"):
            path = reverse("geo_api:location_geojson")
            with self.assertNumQueries(3):
                response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 1)
            location_features = response.data["features"][0]
            self.assertNotIn("is_estimated", location_features["properties"])

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    def test_estimated_location_filter_list_api(self):
        org = self._get_org()
        location1 = self._create_location(
            name="location1", is_estimated=True, organization=org
        )
        location2 = self._create_location(
            name="location2", is_estimated=False, organization=org
        )
        location3 = self._create_location(
            name="location3", is_estimated=False, organization=org
        )
        device1 = self._create_device()
        device2 = self._create_device(
            name="11:22:33:44:55:66", mac_address="11:22:33:44:55:66"
        )
        self._create_object_location(content_object=device1, location=location1)
        self._create_object_location(content_object=device2, location=location2)
        path = reverse("geo_api:list_location")

        with self.subTest(
            "Test Estimated Location filter available in location list "
            "when WHOIS is configured"
        ):
            with self.assertNumQueries(4):
                response = self.client.get(path, {"is_estimated": True})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 1)
            self.assertContains(response, location1.id)
            self.assertNotContains(response, location2.id)
            self.assertNotContains(response, location3.id)

        with mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", False):
            with self.subTest(
                "Test Estimated Location filter not available in location list "
                "when WHOIS not configured"
            ):
                with self.assertNumQueries(4):
                    response = self.client.get(path, {"is_estimated": True})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["count"], 3)
                self.assertContains(response, location1.id)
                self.assertContains(response, location2.id)

        path = reverse("config_api:device_list")

        with self.subTest(
            "Test Estimated Location filter available in device list "
            "when WHOIS is configured"
        ):
            with self.assertNumQueries(3):
                response = self.client.get(path, {"geo_is_estimated": True})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 1)
            self.assertContains(response, device1.id)
            self.assertNotContains(response, device2.id)

        with mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", False):
            with self.subTest(
                "Test Estimated Location filter not available in device list "
                "when WHOIS not configured"
            ):
                with self.assertNumQueries(3):
                    response = self.client.get(path, {"geo_is_estimated": True})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["count"], 2)
                self.assertContains(response, device1.id)
                self.assertContains(response, device2.id)

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    def test_location_admin_estimated_field(self):
        org = self._get_org()
        estimated_location = self._create_location(
            name="location1", is_estimated=True, organization=org
        )
        estimated_device = self._create_device()
        self._create_object_location(
            content_object=estimated_device, location=estimated_location
        )
        path = reverse("admin:geo_location_changelist")
        response = self.client.get(path)

        with self.subTest("Test location Admin estimated field displayed"):
            self.assertContains(response, "column-is_estimated")

        with self.subTest("Test location admin estimated field sorting enabled"):
            self.assertContains(response, "sortable column-is_estimated")

        with mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", False):
            response = self.client.get(path)
            with self.subTest(
                "Test location admin estimated field not displayed "
                "when WHOIS not configured"
            ):
                self.assertNotContains(response, "column-is_estimated")

            with self.subTest(
                "Test location admin estimated field sorting not enabled "
                "when WHOIS not configured"
            ):
                self.assertNotContains(response, "sortable column-is_estimated")

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    def test_estimated_location_filter_admin(self):
        org = self._get_org()
        estimated_location = self._create_location(
            name="location1", is_estimated=True, organization=org
        )
        outdoor_location = self._create_location(name="location2", organization=org)
        indoor_location = self._create_location(
            name="location3", organization=org, type="indoor"
        )
        estimated_device = self._create_device()
        outdoor_device = self._create_device(
            name="11:22:33:44:55:66", mac_address="11:22:33:44:55:66"
        )
        indoor_device = self._create_device(
            name="11:22:33:44:55:77", mac_address="11:22:33:44:55:77"
        )
        self._create_object_location(
            content_object=estimated_device, location=estimated_location
        )
        self._create_object_location(
            content_object=outdoor_device, location=outdoor_location
        )
        self._create_object_location(
            content_object=indoor_device, location=indoor_location
        )
        path = reverse("admin:config_device_changelist")

        with self.subTest("Test All Locations Filter"):
            response = self.client.get(path)
            self.assertContains(response, estimated_device.id)
            self.assertContains(response, outdoor_device.id)
            self.assertContains(response, indoor_device.id)
            self.assertContains(response, "3 Devices")

        with self.subTest("Test Estimated Location Filter"):
            response = self.client.get(path, {"with_geo": "estimated"})
            self.assertContains(response, estimated_device.id)
            self.assertNotContains(response, outdoor_device.id)
            self.assertNotContains(response, indoor_device.id)
            self.assertContains(response, "1 Device")

        with self.subTest("Test Outdoor Location Filter"):
            response = self.client.get(path, {"with_geo": "outdoor"})
            self.assertContains(response, outdoor_device.id)
            self.assertNotContains(response, estimated_device.id)
            self.assertNotContains(response, indoor_device.id)
            self.assertContains(response, "1 Device")

        with self.subTest("Test Indoor Location Filter"):
            response = self.client.get(path, {"with_geo": "indoor"})
            self.assertContains(response, indoor_device.id)
            self.assertNotContains(response, outdoor_device.id)
            self.assertNotContains(response, estimated_device.id)
            self.assertContains(response, "1 Device")

        with self.subTest("Test No Location Filter"):
            response = self.client.get(path, {"with_geo": "false"})
            self.assertNotContains(response, indoor_device.id)
            self.assertNotContains(response, outdoor_device.id)
            self.assertNotContains(response, estimated_device.id)
            self.assertContains(response, "0 Devices")

        with mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", False):
            with self.subTest(
                "Test Estimated Location Admin specific filters not available"
                " when WHOIS not configured"
            ):
                for filter_value in ["estimated", "outdoor", "indoor"]:
                    with self.subTest(filter_value=filter_value):
                        response = self.client.get(path, {"with_geo": filter_value})
                        self.assertContains(response, estimated_device.id)
                        self.assertContains(response, outdoor_device.id)
                        self.assertContains(response, indoor_device.id)
                        self.assertContains(response, "3 Devices")
