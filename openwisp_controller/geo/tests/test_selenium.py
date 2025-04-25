from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django_loci.tests.base.test_selenium import BaseTestDeviceAdminSelenium
from selenium.webdriver.common.by import By
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin

Device = load_model('config', 'Device')
Location = load_model('geo', 'Location')
FloorPlan = load_model('geo', 'FloorPlan')
DeviceLocation = load_model('geo', 'DeviceLocation')


class TestDeviceAdminSelenium(
    BaseTestDeviceAdminSelenium, TestOrganizationMixin, StaticLiveServerTestCase
):
    app_label = 'geo'
    object_model = Device
    location_model = Location
    object_location_model = DeviceLocation
    user_model = get_user_model()

    inline_field_prefix = 'devicelocation'

    @classmethod
    def _get_prefix(cls):
        return cls.inline_field_prefix

    def _fill_device_form(self):
        org = self._get_org()
        self.find_element(by=By.NAME, value='mac_address').send_keys(
            '11:22:33:44:55:66'
        )
        self.find_element(
            by=By.CSS_SELECTOR, value='#select2-id_organization-container'
        ).click()
        self.wait_for_invisibility(
            By.CSS_SELECTOR, '.select2-results__option.loading-results'
        )
        self.find_element(by=By.CLASS_NAME, value='select2-search__field').send_keys(
            org.name
        )
        self.wait_for_invisibility(
            By.CSS_SELECTOR, '.select2-results__option.loading-results'
        )
        self.find_element(by=By.CLASS_NAME, value='select2-results__option').click()
        super()._fill_device_form()
