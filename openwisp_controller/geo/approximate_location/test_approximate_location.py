import importlib
from unittest import mock

from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from swapper import load_model

from openwisp_controller.config import settings as config_app_settings
from openwisp_controller.config.whois.handlers import connect_whois_handlers
from openwisp_controller.config.whois.utils import WHOISTransactionMixin

from ...tests.utils import TestAdminMixin
from .utils import TestApproximateLocationMixin

Device = load_model("config", "Device")
Location = load_model("geo", "Location")
Notification = load_model("openwisp_notifications", "Notification")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")

notification_qs = Notification.objects.all()


class TestApproximateLocation(TestAdminMixin, TestCase):
    @override_settings(
        OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT="test_account",
        OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY="test_key",
    )
    def test_approximate_location_configuration_setting(self):
        # reload app_settings to apply the overridden settings
        importlib.reload(config_app_settings)
        with self.subTest(
            "ImproperlyConfigured raised when APPROXIMATE_LOCATION_ENABLED is True "
            "and WHOIS_ENABLED is False globally"
        ):
            with override_settings(
                OPENWISP_CONTROLLER_WHOIS_ENABLED=False,
                OPENWISP_CONTROLLER_APPROXIMATE_LOCATION_ENABLED=True,
            ):
                with self.assertRaises(ImproperlyConfigured):
                    # reload app_settings to apply the overridden settings
                    importlib.reload(config_app_settings)

        with self.subTest(
            "Test WHOIS not enabled does not allow enabling Approximate Location"
        ):
            org_settings_obj = OrganizationConfigSettings(organization=self._get_org())
            with self.assertRaises(ValidationError) as context_manager:
                org_settings_obj.whois_enabled = False
                org_settings_obj.approximate_location_enabled = True
                org_settings_obj.full_clean()
            try:
                self.assertEqual(
                    context_manager.exception.message_dict[
                        "approximate_location_enabled"
                    ][0],
                    "Approximate Location feature requires "
                    + "WHOIS Lookup feature to be enabled.",
                )
            except AssertionError:
                self.fail("ValidationError message not equal to expected message.")

        with self.subTest(
            "Test Approximate Location field visible on admin when "
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
                response, 'name="config_settings-0-approximate_location_enabled"'
            )

        with override_settings(
            OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT=None,
            OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY=None,
        ):
            importlib.reload(config_app_settings)
            with self.subTest(
                "Test Approximate Location field hidden on admin when "
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
                    response, 'name="config_settings-0-approximate_location_enabled"'
                )


class TestApproximateLocationTransaction(
    TestApproximateLocationMixin, WHOISTransactionMixin, TransactionTestCase
):
    _WHOIS_GEOIP_CLIENT = (
        "openwisp_controller.config.whois.tasks.geoip2_webservice.Client"
    )

    def setUp(self):
        super().setUp()
        self.admin = self._get_admin()

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(
        "openwisp_controller.geo.approximate_location.tasks.manage_approximate_locations.delay"  # noqa
    )
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_approximate_location_task_called(
        self, mocked_client, mocked_approximate_location_task
    ):
        connect_whois_handlers()
        mocked_client.return_value.city.return_value = self._mocked_client_response()

        self._task_called(
            mocked_approximate_location_task, task_name="Approximate location"
        )

        Device.objects.all().delete()
        device = self._create_device()
        with self.subTest(
            "Approximate location task called when last_ip has related WhoIsInfo"
        ):
            device.organization.config_settings.whois_enabled = True
            device.organization.config_settings.approximate_location_enabled = True
            device.organization.config_settings.save()
            device.last_ip = "172.217.22.14"
            self._create_whois_info(ip_address=device.last_ip)
            device.save()
            mocked_approximate_location_task.assert_called()
        mocked_approximate_location_task.reset_mock()

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_approximate_location_creation_and_update(self, mock_client):
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

        with self.subTest("Test Approximate location created when device is created"):
            device = self._create_device(last_ip="172.217.22.14")

            location = device.devicelocation.location
            mocked_response.ip_address = device.last_ip
            self.assertEqual(location.is_approximate, True)
            self.assertEqual(location.is_mobile, False)
            self.assertEqual(location.type, "outdoor")
            _verify_location_details(device, mocked_response)

        with self.subTest("Test Approximate location updated when last ip is updated"):
            device.last_ip = "172.217.22.10"
            mocked_response.location.latitude = 50
            mocked_response.location.longitude = 150
            mocked_response.city.name = "New City"
            mock_client.return_value.city.return_value = mocked_response
            device.save()
            device.refresh_from_db()

            location = device.devicelocation.location
            mocked_response.ip_address = device.last_ip
            self.assertEqual(location.is_approximate, True)
            self.assertEqual(location.is_mobile, False)
            self.assertEqual(location.type, "outdoor")
            _verify_location_details(device, mocked_response)

        with self.subTest(
            "Test Location not updated if it is not approximate when last ip is updated"
        ):
            mocked_response.ip_address = device.last_ip
            device.last_ip = "172.217.22.11"
            device.devicelocation.location.is_approximate = False
            mock_client.return_value.city.return_value = self._mocked_client_response()
            device.devicelocation.location.save()
            device.save()
            device.refresh_from_db()

            location = device.devicelocation.location
            self.assertEqual(location.is_approximate, False)
            self.assertEqual(location.is_mobile, False)
            self.assertEqual(location.type, "outdoor")
            _verify_location_details(device, mocked_response)

        with self.subTest(
            "Test location shared for same IP when new device's location does not exist"
        ):
            Device.objects.all().delete()
            device1 = self._create_device(last_ip="172.217.22.10")
            device2 = self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.10",
            )

            self.assertEqual(
                device1.devicelocation.location.pk, device2.devicelocation.location.pk
            )

        with self.subTest(
            "Test location shared for same IP when new device's location is approximate"
        ):
            Device.objects.all().delete()
            device1 = self._create_device(last_ip="172.217.22.10")
            device2 = self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.11",
            )
            old_location = device2.devicelocation.location
            device2.last_ip = "172.217.22.10"
            device2.save()
            device2.refresh_from_db()

            self.assertEqual(
                device1.devicelocation.location.pk, device2.devicelocation.location.pk
            )
            self.assertEqual(Location.objects.filter(pk=old_location.pk).count(), 0)

        with self.subTest(
            "Test location not shared for same IP when new "
            "device's location is not approximate"
        ):
            Device.objects.all().delete()
            device1 = self._create_device(last_ip="172.217.22.10")
            device2 = self._create_device(
                name="11:22:33:44:55:66",
                mac_address="11:22:33:44:55:66",
                last_ip="172.217.22.11",
            )
            old_location = device2.devicelocation.location
            old_location.is_approximate = False
            old_location.save()
            device2.last_ip = "172.217.22.10"
            device2.save()
            device2.refresh_from_db()

            self.assertNotEqual(
                device1.devicelocation.location.pk, device2.devicelocation.location.pk
            )
            self.assertEqual(Location.objects.filter(pk=old_location.pk).count(), 1)

    @mock.patch.object(config_app_settings, "WHOIS_CONFIGURED", True)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_approximate_location_notification(self, mock_client):
        """
        For testing notification related to location is sent to user
        when already multiple devices with same last_ip exist.
        """
        mocked_response = self._mocked_client_response()
        mock_client.return_value.city.return_value = mocked_response
        self._create_device(last_ip="172.217.22.10")
        # will have same location as first device
        self._create_device(
            name="11:22:33:44:55:66",
            mac_address="11:22:33:44:55:66",
            last_ip="172.217.22.10",
        )
        # device3 will not have same location as first two devices
        # as multiple devices found for same last_ip causing conflict
        device3 = self._create_device(
            name="11:22:33:44:55:77",
            mac_address="11:22:33:44:55:77",
            last_ip="172.217.22.10",
        )
        self.assertEqual(notification_qs.count(), 1)
        notification = notification_qs.first()
        self.assertEqual(notification.actor, device3)
        self.assertEqual(notification.target, device3)
        self.assertEqual(notification.type, "generic_message")
        self.assertEqual(notification.level, "error")
        self.assertIn(
            "Unable to create approximate location for device",
            notification.message,
        )
        self.assertIn(device3.last_ip, notification.description)
