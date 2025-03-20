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
from openwisp_utils.tests import SeleniumTestMixin

Device = load_model('config', 'Device')
DeviceConnection = load_model('connection', 'DeviceConnection')
Location = load_model('geo', 'Location')
FloorPlan = load_model('geo', 'FloorPlan')
DeviceLocation = load_model('geo', 'DeviceLocation')


@tag('selenium_tests')
class TestDevice(
    CreateConnectionsMixin, TestGeoMixin, SeleniumTestMixin, StaticLiveServerTestCase
):
    config_app_label = 'config'
    location_model = Location
    object_location_model = DeviceLocation
    floorplan_model = FloorPlan

    def setUp(self):
        self.admin = self._create_admin(
            username=self.admin_username, password=self.admin_password
        )

    @patch('reversion.models.logger.warning')
    def test_restoring_deleted_device(self, *args):
        org = self._get_org()
        self._create_credentials(auto_add=True, organization=org)
        config = self._create_config(organization=org)
        device = config.device

        location = self._create_location(organization=org, type='indoor')
        floorplan = self._create_floorplan(
            location=location,
        )
        self._create_object_location(
            location=location,
            floorplan=floorplan,
            content_object=device,
        )
        self.assertEqual(device.deviceconnection_set.count(), 1)
        call_command('createinitialrevisions')

        self.login()
        # Delete the device
        device.deactivate()
        config.set_status_deactivated()
        self.open(
            reverse(f'admin:{self.config_app_label}_device_delete', args=[device.id])
        )
        self.find_element(
            by=By.CSS_SELECTOR, value='#content form input[type="submit"]'
        ).click()
        # Delete location object
        location.delete()
        self.assertEqual(Device.objects.count(), 0)
        self.assertEqual(DeviceConnection.objects.count(), 0)
        self.assertEqual(DeviceLocation.objects.count(), 0)
        self.assertEqual(self.location_model.objects.count(), 0)
        self.assertEqual(self.floorplan_model.objects.count(), 0)

        version_obj = Version.objects.get_deleted(model=Device).first()

        # Restore deleted device
        self.open(
            reverse(
                f'admin:{self.config_app_label}_device_recover', args=[version_obj.id]
            )
        )
        # The StaticLiveServerTestCase class only starts a server for Django and
        # does not support websockets (channels). This causes multiple errors to
        # be logged when trying to establish a WebSocket connection at SEVERE level,
        # which is problematic because the error for the issue described in
        # https://github.com/openwisp/openwisp-controller/issues/681
        # is logged at WARNING level.
        # By checking that there are no WARNING level errors logged in the
        # browser console, we ensure that this issue is not happening.
        for error in self.get_browser_logs():
            if error['level'] == 'WARNING' and error['message'] not in [
                'wrong event specified: touchleave'
            ]:
                self.fail(f'Browser console error: {error["message"]}')
        self.find_element(
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
        self.assertEqual(self.location_model.objects.count(), 1)
        # The FloorPlan object is not recoverable because deleting it
        # also removes the associated image from the filesystem,
        # which cannot be restored.
        self.assertEqual(self.floorplan_model.objects.count(), 0)
