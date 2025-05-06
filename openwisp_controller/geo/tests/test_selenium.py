from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls.base import reverse
from django_loci.tests import TestAdminMixin
from django_loci.tests.base.test_selenium import BaseTestDeviceAdminSelenium
from selenium.webdriver.common.by import By
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin
from openwisp_utils.tests import SeleniumTestMixin

from .utils import TestGeoMixin

Device = load_model('config', 'Device')
Location = load_model('geo', 'Location')
FloorPlan = load_model('geo', 'FloorPlan')
DeviceLocation = load_model('geo', 'DeviceLocation')


# these tests are for geo elements on device admin
@tag('selenium_tests')
class TestDeviceAdminGeoSelenium(
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

    # set timeout to 5 seconds to allow enough time for presence of elements
    def wait_for_presence(self, by, value, timeout=5, driver=None):
        return super().wait_for_presence(by, value, timeout, driver)

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


@tag('selenium_tests')
class TestDeviceAdminReadonly(
    TestGeoMixin,
    TestAdminMixin,
    SeleniumTestMixin,
    StaticLiveServerTestCase,
):
    browser = 'chrome'
    app_label = 'geo'

    object_model = Device
    location_model = Location
    object_location_model = DeviceLocation
    permission_model = Permission
    user_model = get_user_model()

    # for these tests we need readonly user with view permissions.
    def setUp(self):
        self.admin = self._create_readonly_admin(
            username=self.admin_username,
            password=self.admin_password,
            models=[self.object_model, self.location_model, self.object_location_model],
        )

    def test_unsaved_changes_readonly(self):
        self.login()
        ol = self._create_object_location()
        path = reverse('admin:config_device_change', args=[ol.device.id])

        with self.subTest('Alert should not be displayed without any change'):
            self.open(path)
            self.hide_loading_overlay()
            # The WebDriver automatically accepts the
            # beforeunload confirmation dialog. To verify the message,
            # we log it to the console and check its content.
            #
            # our own JS code sets e.returnValue when triggered
            # so we just need to ensure it's set as expected
            self.web_driver.execute_script(
                'django.jQuery(window).on("beforeunload", function(e) {'
                ' console.warn(e.returnValue); });'
            )
            self.web_driver.refresh()
            for entry in self.get_browser_logs():
                if (
                    entry['level'] == 'WARNING'
                    and "You haven\'t saved your changes yet!" in entry['message']
                ):
                    self.fail('Unsaved changes alert displayed without any change')
