from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.urls.base import reverse
from reversion.models import Version
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from swapper import load_model

from openwisp_controller.connection.tests.utils import CreateConnectionsMixin
from openwisp_controller.geo.tests.utils import TestGeoMixin

Device = load_model('config', 'Device')
DeviceConnection = load_model('connection', 'DeviceConnection')
Location = load_model('geo', 'Location')
DeviceLocation = load_model('geo', 'DeviceLocation')


class SeleniumTestMixin:
    """
    A base test case for Selenium, providing helped methods for generating
    clients and logging in profiles.
    """

    def open(self, url, driver=None):
        """
        Opens a URL
        Argument:
            url: URL to open
            driver: selenium driver (default: cls.base_driver)
        """
        if not driver:
            driver = self.web_driver
        driver.get(f'{self.live_server_url}{url}')

    def login(self, username=None, password=None, driver=None):
        """
        Log in to the admin dashboard
        Argument:
            driver: selenium driver (default: cls.web_driver)
            username: username to be used for login (default: cls.admin.username)
            password: password to be used for login (default: cls.admin.password)
        """
        if not driver:
            driver = self.web_driver
        if not username:
            username = self.admin_username
        if not password:
            password = self.admin_password
        driver.get(f'{self.live_server_url}/admin/login/')
        if 'admin/login' in driver.current_url:
            driver.find_element(by=By.NAME, value='username').send_keys(username)
            driver.find_element(by=By.NAME, value='password').send_keys(password)
            driver.find_element(by=By.XPATH, value='//input[@type="submit"]').click()


class TestDeviceConnectionInlineAdmin(
    CreateConnectionsMixin, TestGeoMixin, SeleniumTestMixin, StaticLiveServerTestCase
):
    config_app_label = 'config'
    admin_username = 'admin'
    admin_password = 'password'
    location_model = Location
    object_location_model = DeviceLocation

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chrome_options = webdriver.ChromeOptions()
        if getattr(settings, 'SELENIUM_HEADLESS', True):
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--window-size=1366,768')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--remote-debugging-port=9222')
        capabilities = DesiredCapabilities.CHROME
        capabilities['goog:loggingPrefs'] = {'browser': 'ALL'}
        cls.web_driver = webdriver.Chrome(
            options=chrome_options, desired_capabilities=capabilities
        )

    @classmethod
    def tearDownClass(cls):
        cls.web_driver.quit()
        super().tearDownClass()

    def setUp(self):
        self.admin = self._create_admin(
            username=self.admin_username, password=self.admin_password
        )

    def tearDown(self):
        # Accept unsaved changes alert to allow other tests to run
        try:
            self.web_driver.refresh()
        except UnexpectedAlertPresentException:
            alert = Alert(self.web_driver)
            alert.accept()
        else:
            try:
                WebDriverWait(self.web_driver, 1).until(EC.alert_is_present())
            except TimeoutException:
                pass
            else:
                alert = Alert(self.web_driver)
                alert.accept()
        self.web_driver.refresh()
        WebDriverWait(self.web_driver, 2).until(
            EC.visibility_of_element_located((By.XPATH, '//*[@id="site-name"]'))
        )

    def test_restoring_deleted_device(self):
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
