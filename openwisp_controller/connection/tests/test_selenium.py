from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls import reverse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from swapper import load_model

from openwisp_utils.tests import SeleniumTestMixin

from .utils import CreateCommandMixin

Command = load_model("connection", "Command")


@tag("selenium_tests")
class TestDeviceAdmin(
    CreateCommandMixin,
    SeleniumTestMixin,
    StaticLiveServerTestCase,
):
    config_app_label = "config"

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
        path = reverse(f"admin:{self.config_app_label}_device_change", args=[device.id])
        self.open(path)
        self.hide_loading_overlay()
        # The "Send Command" widget is not visible on devices which do
        # not have a DeviceConnection object
        self.wait_for_invisibility(By.CSS_SELECTOR, "ul.object-tools a#send-command")
        self._create_device_connection(device=device, credentials=creds)
        self.assertEqual(device.deviceconnection_set.count(), 1)
        self.open(path)
        self.hide_loading_overlay()
        # Send reboot command to the device
        self.find_element(
            by=By.CSS_SELECTOR, value="ul.object-tools a#send-command"
        ).click()
        self.find_element(
            by=By.CSS_SELECTOR, value='button.ow-command-btn[data-command="reboot"]'
        ).click()
        self.find_element(by=By.CSS_SELECTOR, value="#ow-command-confirm-yes").click()

        self.assertEqual(Command.objects.count(), 1)
        # TODO: Selenium tests do not support websocket connections.
        # Thus, we need to refresh the page. Remove this when support for
        # websockets is added.
        self.open(path)
        self.wait_for_visibility(
            By.CSS_SELECTOR,
            "#tabs-container li.recent.commands",
        )

    def test_device_form_shows_command_input_as_text(self):
        org = self._get_org()
        device_conn = self._create_device_connection(
            device=self._create_config(organization=org).device,
            credentials=self._create_credentials(organization=org),
        )
        self._create_command(device_conn=device_conn)
        command = '<b class="injected">injected-command</b>'
        self.login()
        self.open(
            reverse(
                f"admin:{self.config_app_label}_device_change",
                args=[device_conn.device_id],
            )
        )
        self.hide_loading_overlay()
        self.find_element(
            by=By.CSS_SELECTOR, value="ul.object-tools a#send-command"
        ).click()
        self.find_element(
            by=By.CSS_SELECTOR, value='button.ow-command-btn[data-command="custom"]'
        ).click()
        self.find_element(
            by=By.CSS_SELECTOR,
            value='#id_command_set-0-input_jsoneditor input[name="root[command]"]',
        ).send_keys(command, Keys.TAB)
        self.find_element(by=By.CSS_SELECTOR, value="#ow-command-submit-btn").click()
        self.wait_for_visibility(
            By.XPATH,
            '//div[contains(@class,"dynamic-command_set-2")]'
            '//div[contains(@class,"field-input")]'
            '//div[contains(.,"injected-command")]',
        )
        inputs = [
            element.text
            for element in self.find_elements(
                by=By.CSS_SELECTOR,
                value=".dynamic-command_set-2 .field-input .readonly",
            )
        ]
        self.assertIn(command, inputs, "the command input is not displayed as text")
        self.assertFalse(
            self.web_driver.find_elements(
                By.CSS_SELECTOR, "#command_set-2-group .injected"
            ),
            "the command input was rendered as HTML",
        )
