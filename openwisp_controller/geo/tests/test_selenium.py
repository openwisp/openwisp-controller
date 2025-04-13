from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django_loci.tests.base.test_selenium import BaseTestDeviceAdminSelenium
from selenium.webdriver.common.by import By
from swapper import load_model

Device = load_model('config', 'Device')
Location = load_model('geo', 'Location')
FloorPlan = load_model('geo', 'FloorPlan')
DeviceLocation = load_model('geo', 'DeviceLocation')


class TestDeviceAdminSelenium(BaseTestDeviceAdminSelenium, StaticLiveServerTestCase):
    app_label = 'geo'
    object_model = Device
    location_model = Location
    object_location_model = DeviceLocation
    user_model = get_user_model()

    inline_field_prefix = 'devicelocation'

    @classmethod
    def _get_prefix(cls):
        return cls.inline_field_prefix

    def _create_device(self):
        self.find_element(by=By.NAME, value='mac_address').send_keys(
            '11:22:33:44:55:66'
        )
        super()._create_device()
