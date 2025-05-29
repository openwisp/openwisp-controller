from unittest import mock

from django.test import TransactionTestCase
from swapper import load_model

from .. import settings as app_settings
from ..tasks import fetch_whois_details
from .utils import CreateDeviceMixin

Device = load_model("config", "Device")
WhoIsInfo = load_model("config", "WhoIsInfo")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")


class TestWhoIsInfo(CreateDeviceMixin, TransactionTestCase):
    _WHOIS_GEOIP_CLIENT = "openwisp_controller.config.tasks.geoip2_webservice.Client"
    _WHOIS_TASKS_INFO_LOGGER = "openwisp_controller.config.tasks.logger.info"

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

    @mock.patch.object(fetch_whois_details, "delay")
    def test_task_called(self, mocked_task):
        org = self._get_org()
        OrganizationConfigSettings.objects.create(organization=org, whois_enabled=True)

        with self.subTest("task called when last_ip is public"):
            device = self._create_device(last_ip="172.217.22.14")
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
            org.config_settings.whois_enabled = False
            org.config_settings.save()
            device.refresh_from_db()
            device.last_ip = "172.217.22.14"
            device.save()
            mocked_task.assert_not_called()
        mocked_task.reset_mock()

    # mocking the geoip2 client to return a mock response
    @mock.patch(_WHOIS_TASKS_INFO_LOGGER)
    @mock.patch(_WHOIS_GEOIP_CLIENT)
    def test_whois_info_creation_task(self, mock_client, mock_info):
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
        device = self._create_device(last_ip="172.217.22.14")
        self.assertEqual(mock_info.call_count, 1)
        device.refresh_from_db()

        # fetching the WhoIs info for the device
        whois_info = device.whois_info
        self.assertEqual(whois_info.organization_name, "Google LLC")
        self.assertEqual(whois_info.asn, "15169")
        self.assertEqual(whois_info.country, "United States")
        self.assertEqual(whois_info.timezone, "America/Los_Angeles")
        self.assertEqual(
            whois_info.address, "Mountain View, United States, North America, 94043"
        )
        self.assertEqual(whois_info.cidr, "172.217.22.0/24")
        self.assertEqual(whois_info.ip_address, "172.217.22.14")
