from unittest import mock

from django.test import TransactionTestCase
from swapper import load_model

from ..tasks import fetch_whois_details
from .utils import CreateDeviceMixin

Device = load_model("config", "Device")
WHOISInfo = load_model("config", "WHOISInfo")


class TestWHOISInfo(CreateDeviceMixin, TransactionTestCase):
    @mock.patch.object(fetch_whois_details, "delay")
    def test_task_called(self, mocked_task):
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

    def test_whois_info_creation(self):
        # mocking the geoip2 client to return a mock response
        with mock.patch(
            "openwisp_controller.config.tasks.geoip2.webservice.Client"
        ) as mock_client:
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
            device.refresh_from_db()

            # fetching the WHOIS info for the device
            whois_info = device.whois_info
            self.assertEqual(whois_info.organization_name, "Google LLC")
            self.assertEqual(whois_info.asn, "15169")
            self.assertEqual(whois_info.country, "United States")
            self.assertEqual(whois_info.timezone, "America/Los_Angeles")
            self.assertEqual(
                whois_info.address, "Mountain View, United States, North America, 94043"
            )
            self.assertEqual(whois_info.cidr, "172.217.22.0/24")
            self.assertEqual(whois_info.last_public_ip, "172.217.22.14")
