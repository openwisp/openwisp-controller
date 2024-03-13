from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls import reverse
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from swapper import load_model

from openwisp_utils.test_selenium_mixins import SeleniumTestMixin

from .utils import CreateConnectionsMixin

Command = load_model('connection', 'Command')


@tag('selenium_tests')
class TestDeviceAdmin(
    CreateConnectionsMixin,
    SeleniumTestMixin,
    StaticLiveServerTestCase,
):
    config_app_label = 'config'

    def setUp(self):
        self.admin = self._create_admin(
            username=self.admin_username, password=self.admin_password
        )

    def test_command_widget_on_device(self):
        """
        This test checks that the "Send Command" widget is only visible when
        a device has a DeviceConnection object.
        It also checks sending a "Reboot" command to a device and checks
        that the command is executed successfully.
        """
        org = self._get_org()
        creds = self._create_credentials(organization=org)
        device = self._create_config(organization=org).device
        self.login()
        path = reverse(f'admin:{self.config_app_label}_device_change', args=[device.id])
        self.open(path)
        # The "Send Command" widget is not visible on devices which do
        # not have a DeviceConnection object
        WebDriverWait(self.web_driver, 2).until(
            EC.invisibility_of_element_located(
                (By.CSS_SELECTOR, 'ul.object-tools a#send-command')
            )
        )
        self._create_device_connection(device=device, credentials=creds)
        self.web_driver.refresh()
        WebDriverWait(self.web_driver, 2).until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, 'ul.object-tools a#send-command')
            )
        )
        # Send reboot command to the device
        self.web_driver.find_element(
            by=By.CSS_SELECTOR, value='ul.object-tools a#send-command'
        ).click()
        self.web_driver.find_element(
            by=By.CSS_SELECTOR, value='button.ow-command-btn[data-command="reboot"]'
        ).click()
        self.web_driver.find_element(
            by=By.CSS_SELECTOR, value='#ow-command-confirm-yes'
        ).click()
        WebDriverWait(self.web_driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, '#command_set-2-group'))
        )
        self.assertEqual(Command.objects.count(), 1)
