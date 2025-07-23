import importlib
from unittest import mock

from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from swapper import load_model

from openwisp_controller.config import settings as config_app_settings
from openwisp_controller.config.whois.handlers import connect_whois_handlers
from openwisp_controller.config.whois.tests_utils import WHOISTransactionMixin

from ...tests.utils import TestAdminMixin
from ..tests.utils import TestGeoMixin
from .tests_utils import TestEstimatedLocationMixin

Device = load_model("config", "Device")
Location = load_model("geo", "Location")
WHOISInfo = load_model("config", "WHOISInfo")
Notification = load_model("openwisp_notifications", "Notification")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")

notification_qs = Notification.objects.all()


class TestEstimatedLocation(TestAdminMixin, TestCase):
    @override_settings(
        OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT="test_account",
        OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY="test_key",
    )
    def test_estimated_location_configuration_setting(self):
        # reload app_settings to apply the overridden settings
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
            try:
                self.assertEqual(
                    context_manager.exception.message_dict[
                        "estimated_location_enabled"
                    ][0],
                    "Estimated Location feature requires "
                    + "WHOIS Lookup feature to be enabled.",
                )
            except AssertionError:
                self.fail("ValidationError message not equal to expected message.")

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
        try:
            self.assertEqual(
                context_manager.exception.message_dict["is_estimated"][0],
                "Estimated Location feature required to be configured.",
            )
        except AssertionError:
            self.fail("ValidationError message not equal to expected message.")

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    def test_estimated_location_admin(self):
        connect_whois_handlers()
        admin = self._create_admin()
        self.client.force_login(admin)
        org = self._get_org()
        location = self._create_location(organization=org, is_estimated=True)
        path = reverse("admin:geo_location_change", args=[location.pk])
        response = self.client.get(path)
        self.assertContains(response, "field-is_estimated")
        self.assertContains(
            response, "Whether the location's coordinates are estimated."
        )
        org.config_settings.estimated_location_enabled = False
        org.config_settings.save()
        response = self.client.get(path)
        self.assertNotContains(response, "field-is_estimated")
        self.assertNotContains(
            response, "Whether the location's coordinates are estimated."
        )


class TestEstimatedLocationTransaction(
    TestEstimatedLocationMixin, WHOISTransactionMixin, TransactionTestCase
):
    _WHOIS_GEOIP_CLIENT = (
        "openwisp_controller.config.whois.tasks.geoip2_webservice.Client"
    )
    _ESTIMATED_LOCATION_INFO_LOGGER = (
        "openwisp_controller.geo.estimated_location.tasks.logger.info"
    )
    _ESTIMATED_LOCATION_ERROR_LOGGER = (
        "openwisp_controller.geo.estimated_location.tasks.logger.error"
    )

    def setUp(self):
        super().setUp()
        self.admin = self._get_admin()

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(
        "openwisp_controller.geo.estimated_location.tasks.manage_estimated_locations.delay"  # noqa
    )
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_estimated_location_task_called(
        self, mocked_client, mocked_estimated_location_task
    ):
        connect_whois_handlers()
        mocked_client.return_value.city.return_value = self._mocked_client_response()

        self._task_called(
            mocked_estimated_location_task, task_name="Estimated location"
        )

        Device.objects.all().delete()
        device = self._create_device()
        with self.subTest(
            "Estimated location task called when last_ip has related WhoIsInfo"
        ):
            with mock.patch("django.core.cache.cache.get") as mocked_get, mock.patch(
                "django.core.cache.cache.set"
            ) as mocked_set:
                device.organization.config_settings.whois_enabled = True
                device.organization.config_settings.estimated_location_enabled = True
                device.organization.config_settings.save()
                device.last_ip = "172.217.22.14"
                self._create_whois_info(ip_address=device.last_ip)
                device.save()
                mocked_set.assert_not_called()
                # The cache `get` is called twice, once for `whois_enabled` and
                # once for `estimated_location_enabled`
                mocked_get.assert_called()
                mocked_estimated_location_task.assert_called()
        mocked_estimated_location_task.reset_mock()

        with self.subTest(
            "Estimated location task not called via DeviceChecksumView when "
            "last_ip has no related WhoIsInfo"
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
            mocked_estimated_location_task.assert_not_called()
        mocked_estimated_location_task.reset_mock()

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_ESTIMATED_LOCATION_INFO_LOGGER)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_estimated_location_creation_and_update(self, mock_client, mock_info):
        connect_whois_handlers()

        def _verify_location_details(device, mocked_response):
            location = device.devicelocation.location
            mocked_location = mocked_response.location
            address = ", ".join(
                [
                    mocked_response.city.name,
                    mocked_response.country.name,
                    mocked_response.continent.name,
                    mocked_response.postal.code,
                ]
            )
            ip_address = mocked_response.ip_address or device.last_ip
            location_name = (
                ",".join(address.split(",")[:2])
                + f" (Estimated Location: {ip_address})"
            )
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

        with self.subTest(
            "Test Location not updated if it is not estimated when last ip is updated"
        ):
            mocked_response.ip_address = device.last_ip
            device.last_ip = "172.217.22.11"
            device.devicelocation.location.is_estimated = False
            mock_client.return_value.city.return_value = self._mocked_client_response()
            device.devicelocation.location.save()
            device.save()
            device.refresh_from_db()

            location = device.devicelocation.location
            self.assertEqual(location.is_estimated, False)
            self.assertEqual(location.is_mobile, False)
            self.assertEqual(location.type, "outdoor")
            _verify_location_details(device, mocked_response)
            mock_info.assert_not_called()
        mock_info.reset_mock()

        with self.subTest(
            "Test location shared for same IP when new device's location does not exist"
        ):
            Device.objects.all().delete()
            device1 = self._create_device(last_ip="172.217.22.10")
            mock_info.reset_mock()
            device2 = self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.10",
            )

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
            device2 = self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.11",
            )
            mock_info.reset_mock()
            old_location = device2.devicelocation.location
            device2.last_ip = "172.217.22.10"
            device2.save()
            mock_info.assert_called_once_with(
                f"Estimated location saved successfully for {device2.pk}"
                f" for IP: {device2.last_ip}"
            )
            device2.refresh_from_db()

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
            device2 = self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.11",
            )
            mock_info.reset_mock()
            old_location = device2.devicelocation.location
            old_location.is_estimated = False
            old_location.save()
            device2.last_ip = "172.217.22.10"
            device2.save()
            mock_info.assert_not_called()
            device2.refresh_from_db()

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
            device2 = self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.10",
            )
            mock_info.reset_mock()
            self.assertEqual(
                device1.devicelocation.location.pk, device2.devicelocation.location.pk
            )
            device2.last_ip = "172.217.22.11"
            device2.save()
            mock_info.assert_called_once_with(
                f"Estimated location saved successfully for {device2.pk}"
                f" for IP: {device2.last_ip}"
            )
            device2.refresh_from_db()
            self.assertNotEqual(
                device1.devicelocation.location.pk, device2.devicelocation.location.pk
            )
        mock_info.reset_mock()

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_ESTIMATED_LOCATION_INFO_LOGGER)
    @mock.patch(_ESTIMATED_LOCATION_ERROR_LOGGER)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_estimated_location_notification(self, mock_client, mock_error, mock_info):
        def _verify_notification(notification, device, message, notify_type="info"):
            self.assertEqual(notification_qs.count(), 1)
            self.assertEqual(
                notification.actor, device.devicelocation.location or device
            )
            self.assertEqual(notification.target, device)
            self.assertEqual(notification.type, "generic_message")
            self.assertEqual(notification.level, notify_type)
            self.assertIn(message, notification.message)
            self.assertIn(device.last_ip, notification.description)

        with self.subTest("Test Notification for location create"):
            mocked_response = self._mocked_client_response()
            mock_client.return_value.city.return_value = mocked_response
            device1 = self._create_device(last_ip="172.217.22.10")
            notification = notification_qs.first()
            _verify_notification(notification, device1, "created successfully")

        with self.subTest("Test Notification for location update"):
            notification_qs.delete()
            # will have same location as first device
            device2 = self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.10",
            )
            notification = notification_qs.first()
            _verify_notification(notification, device2, "updated successfully")

        with self.subTest("Test Error Notification for conflicting locations"):
            notification_qs.delete()
            mock_info.reset_mock()
            device3 = self._create_device(
                name="11:22:33:44:55:77",
                mac_address="11:22:33:44:55:77",
                last_ip="172.217.22.10",
            )
            mock_info.assert_not_called()
            mock_error.assert_called_once_with(
                f"Multiple devices with locations found with same "
                f"last_ip {device3.last_ip}. Please resolve the conflict manually."
            )
            notification = notification_qs.get(actor_object_id=device3.pk)
            message = "Unable to create estimated location for device"
            _verify_notification(notification, device3, message, "error")
