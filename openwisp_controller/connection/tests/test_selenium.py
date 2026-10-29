from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.test import override_settings, tag
from django.urls import reverse
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from swapper import load_model

from openwisp_utils.tests import SeleniumTestMixin

from ...tests.utils import ControllerLiveServerTestCase
from .utils import CreateCommandMixin

Command = load_model("connection", "Command")


@tag("selenium_tests")
class TestDeviceAdmin(
    CreateCommandMixin,
    SeleniumTestMixin,
    ControllerLiveServerTestCase,
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
        self.wait_for_script(
            "return django._jsonEditors['id_command_set-0-input_jsoneditor']"
            ".getValue().command === arguments[0];",
            command,
        )
        self.find_element(by=By.CSS_SELECTOR, value="#ow-command-submit-btn").click()
        self.wait_until(
            lambda _: Command.objects.filter(
                device_id=device_conn.device_id, input={"command": command}
            ).exists(),
            timeout=5,
        )
        self.wait_for_visibility(
            By.XPATH,
            '//div[contains(@class,"dynamic-command_set-2")]'
            '//div[contains(@class,"field-input")]'
            '//div[contains(.,"injected-command")]',
            timeout=5,
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


@tag("selenium_tests")
@override_settings(
    # Daphne runs in another process, so parent-process updates need Redis.
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [settings.REDIS_URL],
                "prefix": f"controller-selenium-{uuid4().hex}",
            },
        }
    }
)
class TestCommandUpdates(
    CreateCommandMixin, SeleniumTestMixin, ControllerLiveServerTestCase
):
    @patch("openwisp_controller.connection.base.models.launch_command.delay")
    def test_command_update(self, launch_command):
        """Deliver a worker-side update to an existing row without a page reload."""
        command = self._create_command()
        launch_command.assert_called_once_with(command.pk)
        self.login()
        self.open(reverse("admin:config_device_change", args=[command.device_id]))
        self.hide_loading_overlay()
        self.find_element(By.CSS_SELECTOR, 'a[href="#command_set-2-group"]').click()
        row = self.find_element(
            By.XPATH,
            f'//input[@value="{command.pk}"]/parent::div/fieldset',
        )
        output = row.find_element(By.CSS_SELECTOR, ".field-output_data .readonly")
        self.assertEqual(output.text, "")
        self.addCleanup(
            self.web_driver.execute_script,
            "if (window.testCommandSocket) window.testCommandSocket.close();",
        )
        connected = self.web_driver.execute_async_script(
            """
            const done = arguments[arguments.length - 1];
            window.commandUpdateMarker = arguments[1];
            window.testCommandSocket = new WebSocket(arguments[0]);
            testCommandSocket.onopen = () => done(true);
            testCommandSocket.onerror = () => done(false);
            """,
            self.live_server_url.replace("http", "ws", 1)
            + f"/ws/controller/device/{command.device_id}/command",
            str(command.pk),
        )
        self.assertTrue(connected, "Authenticated command WebSocket failed to open")
        command.status = "success"
        command.output = "Live command output"
        command.save()
        try:
            self.wait_until(lambda _: output.text == command.output, timeout=5)
        except TimeoutException:
            self.fail("The command output was not updated through the WebSocket")
        self.assertEqual(
            self.web_driver.execute_script("return window.commandUpdateMarker;"),
            str(command.pk),
            "The command update reloaded the page instead of updating its row",
        )
        self.assert_no_browser_errors()
