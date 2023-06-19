from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.test import tag
from django.urls.base import reverse
from reversion.models import Version
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from swapper import load_model

from openwisp_controller.connection.tests.utils import CreateConnectionsMixin
from openwisp_controller.geo.tests.utils import TestGeoMixin
from openwisp_utils.test_selenium_mixins import SeleniumTestMixin

Device = load_model('config', 'Device')
DeviceConnection = load_model('connection', 'DeviceConnection')
Location = load_model('geo', 'Location')
DeviceLocation = load_model('geo', 'DeviceLocation')


@tag('selenium_tests')
class TestDeviceConnectionInlineAdmin(
    CreateConnectionsMixin, TestGeoMixin, SeleniumTestMixin, StaticLiveServerTestCase
):
    config_app_label = 'config'
    location_model = Location
    object_location_model = DeviceLocation

    def setUp(self):
        self.admin = self._create_admin(
            username=self.admin_username, password=self.admin_password
        )

    @patch('reversion.models.logger.warning')
    def test_restoring_deleted_device(self, *args):
        org = self._get_org()
        self._create_credentials(auto_add=True, organization=org)
        device = self._create_config(organization=org).device
        self._create_object_location(
            location=self._create_location(
                organization=org,
            ),
            content_object=device,
        )
        self.assertEqual(device.deviceconnection_set.count(), 1)
        call_command('createinitialrevisions')

        self.login()
        # Delete the device
        self.open(
            reverse(f'admin:{self.config_app_label}_device_delete', args=[device.id])
        )
        self.web_driver.find_element(
            by=By.XPATH, value='//*[@id="content"]/form/div/input[2]'
        ).click()
        self.assertEqual(Device.objects.count(), 0)
        self.assertEqual(DeviceConnection.objects.count(), 0)
        self.assertEqual(DeviceLocation.objects.count(), 0)

        version_obj = Version.objects.get_deleted(model=Device).first()

        # Restore deleted device
        self.open(
            reverse(
                f'admin:{self.config_app_label}_device_recover', args=[version_obj.id]
            )
        )
        self.web_driver.find_element(
            by=By.XPATH, value='//*[@id="device_form"]/div/div[1]/input[1]'
        ).click()
        try:
            WebDriverWait(self.web_driver, 5).until(
                EC.url_to_be(f'{self.live_server_url}/admin/config/device/')
            )
        except TimeoutException:
            self.fail('Deleted device was not restored')

        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(DeviceConnection.objects.count(), 1)
        self.assertEqual(DeviceLocation.objects.count(), 1)
