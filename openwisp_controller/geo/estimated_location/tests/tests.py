import contextlib
import importlib
from unittest import mock

from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from openwisp_notifications.types import unregister_notification_type
from swapper import load_model

from openwisp_controller.config import settings as config_app_settings
from openwisp_controller.config.whois.handlers import connect_whois_handlers
from openwisp_controller.config.whois.tests.utils import WHOISTransactionMixin

from ....tests.utils import TestAdminMixin
from ...tests.utils import TestGeoMixin
from ..handlers import register_estimated_location_notification_types
from .utils import TestEstimatedLocationMixin

Device = load_model("config", "Device")
Location = load_model("geo", "Location")
DeviceLocation = load_model("geo", "DeviceLocation")
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
        # Unregister the notification type if it was previously registered
        with contextlib.suppress(ImproperlyConfigured):
            unregister_notification_type("estimated_location_info")
        with mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True):
            register_estimated_location_notification_types()

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
            "Test Non Estimated Location not updated when last ip is updated"
        ):
            mocked_response.ip_address = device.last_ip
            device.last_ip = "172.217.22.11"
            device.devicelocation.location.is_estimated = False
            mock_client.return_value.city.return_value = self._mocked_client_response()
            device.devicelocation.location.save(_set_estimated=True)
            device.save()
            device.refresh_from_db()

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
            mock_info.assert_called_once_with(
                f"Non Estimated location already set for {device2.pk}. Update"
                f" location manually as per IP: {device2.last_ip}"
            )
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
        def _verify_notification(device, messages, notify_level="info"):
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
            notification_qs.delete()
            # will have same location as first device
            device2 = self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.10",
            )
            messages = ["Estimated location", "updated successfully"]
            _verify_notification(device2, messages)

        with self.subTest("Test Error Notification for conflicting locations"):
            device2.last_ip = device1.last_ip
            device2.save()
            notification_qs.delete()
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
            messages = ["Unable to create estimated location for device"]
            _verify_notification(device3, messages, "error")

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_estimate_location_status_remove(self, mock_client):
        mocked_response = self._mocked_client_response()
        mock_client.return_value.city.return_value = mocked_response
        device = self._create_device(last_ip="172.217.22.10")
        location = device.devicelocation.location
        self.assertTrue(location.is_estimated)
        org = self._get_org()

        with self.subTest(
            "Test Estimated Status unchanged if Estimated feature is disabled"
        ):
            org.config_settings.estimated_location_enabled = False
            org.config_settings.save()
            location.geometry = GEOSGeometry("POINT(12.512124 41.898903)", srid=4326)
            location.save()
            self.assertTrue(location.is_estimated)
            self.assertIn(f"(Estimated Location: {device.last_ip})", location.name)

        with self.subTest(
            "Test Estimated Status unchanged if Estimated feature is enabled"
            " and desired fields not changed"
        ):
            org.config_settings.estimated_location_enabled = True
            org.config_settings.save()
            location._set_initial_values_for_changed_checked_fields()
            location.type = "outdoor"
            location.is_mobile = True
            location.save()
            self.assertTrue(location.is_estimated)

        with self.subTest(
            "Test Estimated Status changed if Estimated feature is enabled"
            " and desired fields changed"
        ):
            location.geometry = GEOSGeometry("POINT(15.512124 45.898903)", srid=4326)
            location.save()
            self.assertFalse(location.is_estimated)
            self.assertNotIn(f"(Estimated Location: {device.last_ip})", location.name)


class TestEstimatedLocationFieldFilters(
    TestEstimatedLocationMixin, TestGeoMixin, TestCase
):
    location_model = Location
    object_location_model = DeviceLocation

    def setUp(self):
        super().setUp()
        admin = self._create_admin()
        self.client.force_login(admin)

    def _create_device_location(self, **kwargs):
        options = dict()
        options.update(kwargs)
        device_location = self.object_location_model(**options)
        device_location.full_clean()
        device_location.save()
        return device_location

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
        self._create_device_location(content_object=org1_device, location=org1_location)
        self._create_device_location(content_object=org2_device, location=org2_location)

        with self.subTest("Test Estimated Location in Locations List"):
            path = reverse("geo_api:list_location")
            with self.assertNumQueries(5):
                response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 2)
            self.assertContains(response, org1_location.id)
            self.assertContains(response, org2_location.id)
            location1 = response.data["results"][1]
            location2 = response.data["results"][0]
            self.assertIn("is_estimated", location1)
            self.assertNotIn("is_estimated", location2)

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
            for i in response.data["features"]:
                if i["id"] == org1_location.id:
                    self.assertIn("is_estimated", i["properties"])
                    self.assertTrue(i["properties"]["is_estimated"])
                elif i["id"] == org2_location.id:
                    self.assertNotIn("is_estimated", i["properties"])
                    self.assertFalse(i["properties"]["is_estimated"])

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", False)
    def test_estimated_location_api_status_not_configured(self):
        org = self._get_org()
        location = self._create_location(name="org1-location", organization=org)
        device = self._create_device(organization=org)
        self._create_device_location(content_object=device, location=location)

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
            self.assertFalse(location_features["properties"].get("is_estimated", False))

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    def test_estimated_location_filter_list_api(self):
        org = self._get_org()
        location1 = self._create_location(
            name="location1", is_estimated=True, organization=org
        )
        location2 = self._create_location(
            name="location2", is_estimated=False, organization=org
        )
        device1 = self._create_device()
        device2 = self._create_device(
            name="11:22:33:44:55:66", mac_address="11:22:33:44:55:66"
        )
        self._create_device_location(content_object=device1, location=location1)
        self._create_device_location(content_object=device2, location=location2)

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

        with mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", False):
            with self.subTest(
                "Test Estimated Location filter not available in location list "
                "when WHOIS not configured"
            ):
                with self.assertNumQueries(5):
                    response = self.client.get(path, {"is_estimated": True})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["count"], 2)
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
        self._create_device_location(
            content_object=estimated_device, location=estimated_location
        )
        self._create_device_location(
            content_object=outdoor_device, location=outdoor_location
        )
        self._create_device_location(
            content_object=indoor_device, location=indoor_location
        )

        path = reverse("admin:config_device_changelist")
        with self.subTest("Test All Locations Filter"):
            response = self.client.get(path)
            self.assertContains(response, estimated_device.id)
            self.assertContains(response, outdoor_device.id)
            self.assertContains(response, indoor_device.id)

        with self.subTest("Test Estimated Location Filter"):
            response = self.client.get(path, {"with_geo": "estimated"})
            self.assertContains(response, estimated_device.id)
            self.assertNotContains(response, outdoor_device.id)
            self.assertNotContains(response, indoor_device.id)

        with self.subTest("Test Outdoor Location Filter"):
            response = self.client.get(path, {"with_geo": "outdoor"})
            self.assertContains(response, outdoor_device.id)
            self.assertNotContains(response, estimated_device.id)
            self.assertNotContains(response, indoor_device.id)

        with self.subTest("Test Indoor Location Filter"):
            response = self.client.get(path, {"with_geo": "indoor"})
            self.assertContains(response, indoor_device.id)
            self.assertNotContains(response, outdoor_device.id)
            self.assertNotContains(response, estimated_device.id)

        with self.subTest("Test Indoor Location Filter"):
            response = self.client.get(path, {"with_geo": "false"})
            self.assertNotContains(response, indoor_device.id)
            self.assertNotContains(response, outdoor_device.id)
            self.assertNotContains(response, estimated_device.id)

        with mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", False):
            with self.subTest(
                "Test Estimated Location Admin specific filters not available"
                " when WHOIS not configured"
            ):
                for i in ["estimated", "outdoor", "indoor"]:
                    response = self.client.get(path, {"with_geo": i})
                    self.assertContains(response, estimated_device.id)
                    self.assertContains(response, outdoor_device.id)
                    self.assertContains(response, indoor_device.id)
