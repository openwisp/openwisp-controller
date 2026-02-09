import os
import time

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls.base import reverse
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.utils import free_port
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from swapper import load_model

from openwisp_utils.tests import SeleniumTestMixin as BaseSeleniumTestMixin

from .utils import CreateConfigTemplateMixin, TestVpnX509Mixin, TestWireguardVpnMixin

Device = load_model("config", "Device")
DeviceGroup = load_model("config", "DeviceGroup")
Cert = load_model("django_x509", "Cert")


class SeleniumTestMixin(BaseSeleniumTestMixin):
    config_app_label = "config"

    def _select_organization(self, org):
        self.find_element(
            by=By.CSS_SELECTOR, value="#select2-id_organization-container"
        ).click()
        self.wait_for_invisibility(
            By.CSS_SELECTOR, ".select2-results__option.loading-results"
        )
        self.find_element(by=By.CLASS_NAME, value="select2-search__field").send_keys(
            org.name
        )
        self.wait_for_invisibility(
            By.CSS_SELECTOR, ".select2-results__option.loading-results"
        )
        self.find_element(by=By.CLASS_NAME, value="select2-results__option").click()

    def _verify_templates_visibility(self, hidden=None, visible=None):
        hidden = hidden or []
        visible = visible or []
        for template in hidden:
            self.wait_for_invisibility(By.XPATH, f'//*[@value="{template.id}"]')
        for template in visible:
            self.wait_for_visibility(By.XPATH, f'//*[@value="{template.id}"]')


@tag("selenium_tests")
class TestDeviceAdmin(
    SeleniumTestMixin,
    CreateConfigTemplateMixin,
    TestVpnX509Mixin,
    StaticLiveServerTestCase,
):
    # helper function for adding/removing templates
    def _update_template(self, device_id, templates, is_enabled=False):
        self.open(
            reverse(f"admin:{self.config_app_label}_device_change", args=[device_id])
            + "#config-group"
        )
        self.wait_for_presence(By.CSS_SELECTOR, 'input[name="config-0-templates"]')

        # if not is_enabled:
        self.hide_loading_overlay()
        for template in templates:
            template_element = self.find_element(
                By.XPATH, f'//*[@value="{template.id}"][@type="checkbox"]'
            )
            # if enabled by default, assert that the checkbox is selected and enabled
            if is_enabled:
                self.assertEqual(template_element.is_enabled(), True)
                self.assertEqual(template_element.is_selected(), True)
            # enable/disable the checkbox
            template_element.click()

        # Hide user tools because it covers the save button
        self.web_driver.execute_script(
            'document.querySelector("#ow-user-tools").style.display="none"'
        )
        self.find_element(by=By.NAME, value="_save").click()
        self.wait_for_presence(By.CSS_SELECTOR, ".messagelist .success", timeout=5)

    def test_create_new_device(self):
        required_template = self._create_template(name="Required", required=True)
        default_template = self._create_template(name="Default", default=True)
        org = self._get_org()
        self.login()
        self.open(reverse(f"admin:{self.config_app_label}_device_add"))
        self.find_element(by=By.NAME, value="name").send_keys("11:22:33:44:55:66")
        self.find_element(
            by=By.CSS_SELECTOR, value="#select2-id_organization-container"
        ).click()
        self.wait_for_invisibility(
            By.CSS_SELECTOR, ".select2-results__option.loading-results"
        )
        self.find_element(by=By.CLASS_NAME, value="select2-search__field").send_keys(
            org.name
        )
        self.wait_for_invisibility(
            By.CSS_SELECTOR, ".select2-results__option.loading-results"
        )
        self.find_element(by=By.CLASS_NAME, value="select2-results__option").click()
        self.find_element(by=By.NAME, value="mac_address").send_keys(
            "11:22:33:44:55:66"
        )
        self.find_element(
            by=By.XPATH, value='//*[@id="config-group"]/fieldset/div[2]/a'
        ).click()
        try:
            WebDriverWait(self.web_driver, 2).until(
                # This WebDriverWait ensures that Selenium waits until the
                # "config-0-templates" input field on the page gets updated
                # with the IDs of the default and required templates after
                # the user clicks on the "Add another config" link. This update
                # is essential because it signifies that the logic in
                # relevant_template.js has executed successfully, selecting
                # the appropriate default and required templates. This logic
                # also changes the ordering of the templates.
                # Failing to wait for this update could lead to
                # StaleElementReferenceException like in
                # https://github.com/openwisp/openwisp-controller/issues/834
                EC.text_to_be_present_in_element_value(
                    (By.CSS_SELECTOR, 'input[name="config-0-templates"]'),
                    f"{required_template.id},{default_template.id}",
                )
            )
        except TimeoutException:
            self.fail("Relevant templates logic was not executed")
        required_template_element = self.find_element(
            by=By.XPATH, value=f'//*[@value="{required_template.id}"]'
        )
        default_template_element = self.find_element(
            by=By.XPATH, value=f'//*[@value="{default_template.id}"]'
        )
        self.assertEqual(required_template_element.is_enabled(), False)
        self.assertEqual(required_template_element.is_selected(), True)
        self.assertEqual(default_template_element.is_enabled(), True)
        self.assertEqual(default_template_element.is_selected(), True)
        # Hide user tools because it covers the save button
        self.web_driver.execute_script(
            'document.querySelector("#ow-user-tools").style.display="none"'
        )
        self.find_element(by=By.NAME, value="_save").click()
        self.wait_for_presence(By.CSS_SELECTOR, ".messagelist .success", timeout=5)
        self.assertEqual(
            self.find_elements(by=By.CLASS_NAME, value="success")[0].text,
            "The Device “11:22:33:44:55:66” was added successfully.",
        )

    def test_device_preview_keyboard_shortcuts(self):
        device = self._create_config(device=self._create_device(name="Test")).device
        self.login()
        self.open(reverse(f"admin:{self.config_app_label}_device_changelist"))
        try:
            self.open(
                reverse(
                    f"admin:{self.config_app_label}_device_change", args=[device.id]
                )
            )
            self.hide_loading_overlay()
        except TimeoutException:
            self.fail("Device detail page did not load in time")

        with self.subTest("press ALT + P and expect overlay to be shown"):
            actions = ActionChains(self.web_driver)
            actions.key_down(Keys.ALT).send_keys("p").key_up(Keys.ALT).perform()
            self.wait_for_visibility(By.CSS_SELECTOR, ".djnjc-overlay:not(.loading)")

        with self.subTest("press ESC to close preview overlay"):
            actions = ActionChains(self.web_driver)
            actions.send_keys(Keys.ESCAPE).perform()
            self.wait_for_invisibility(By.CSS_SELECTOR, ".djnjc-overlay:not(.loading)")

    def test_multiple_organization_templates(self):
        shared_template = self._create_template(name="shared", organization=None)

        org1 = self._create_org(name="org1", slug="org1")
        org1_required_template = self._create_template(
            name="org1 required", organization=org1, required=True
        )
        org1_default_template = self._create_template(
            name="org1 default", organization=org1, default=True
        )

        org2 = self._create_org(name="org2", slug="org2")
        org2_required_template = self._create_template(
            name="org2 required", organization=org2, required=True
        )
        org2_default_template = self._create_template(
            name="org2 default", organization=org2, default=True
        )

        device = self._create_config(
            device=self._create_device(organization=org1)
        ).device

        self.login()
        self.open(
            reverse(f"admin:{self.config_app_label}_device_change", args=[device.id])
            + "#config-group"
        )
        self.hide_loading_overlay()

        with self.subTest("only org1 and shared templates should be visible"):
            self._verify_templates_visibility(
                hidden=[org2_required_template, org2_default_template],
                visible=[
                    org1_required_template,
                    org1_default_template,
                    shared_template,
                ],
            )

        # Select shared template
        self.find_element(
            by=By.XPATH, value=f'//*[@value="{shared_template.id}"]'
        ).click()

        with self.subTest("changing org should update templates"):
            self.find_element(
                By.CSS_SELECTOR, value='a[href="#overview-group"]'
            ).click()
            self._select_organization(org2)
            self.find_element(
                by=By.CSS_SELECTOR, value='a[href="#config-group"]'
            ).click()
            self._verify_templates_visibility(
                hidden=[
                    org1_required_template,
                    org1_default_template,
                ],
                visible=[
                    org2_required_template,
                    org2_default_template,
                    shared_template,
                ],
            )
            # Verify that shared template is selected
            self.assertEqual(
                self.find_element(
                    by=By.CSS_SELECTOR,
                    value=f'input[type="checkbox"][value="{shared_template.id}"]',
                ).is_selected(),
                True,
            )
            self.find_element(
                by=By.CSS_SELECTOR, value='input[name="_continue"]'
            ).click()
            self._wait_until_page_ready()
            device.refresh_from_db()
            device.config.refresh_from_db()
            self.assertEqual(device.organization, org2)
            self.assertEqual(device.config.templates.count(), 3)
            self.assertIn(org2_required_template, device.config.templates.all())
            self.assertIn(org2_default_template, device.config.templates.all())
            self.assertIn(shared_template, device.config.templates.all())

    def test_change_config_backend(self):
        device = self._create_config(organization=self._get_org()).device
        template = self._create_template()

        self.login()
        self.open(
            reverse(f"admin:{self.config_app_label}_device_change", args=[device.id])
            + "#config-group"
        )
        self.hide_loading_overlay()
        self.find_element(by=By.XPATH, value=f'//*[@value="{template.id}"]')
        # Change config backed to
        config_backend_select = Select(
            self.find_element(by=By.NAME, value="config-0-backend")
        )
        config_backend_select.select_by_visible_text("OpenWISP Firmware 1.x")
        self.wait_for_invisibility(By.XPATH, f'//*[@value="{template.id}"]')

    def test_force_delete_device_with_deactivating_config(self):
        self._create_template(default=True)
        config = self._create_config(organization=self._get_org())
        device = config.device
        self.assertEqual(device.is_deactivated(), False)
        self.assertEqual(config.status, "modified")

        self.login()
        self.open(
            reverse(f"admin:{self.config_app_label}_device_change", args=[device.id])
        )
        self.hide_loading_overlay()
        # The webpage has two "submit-row" sections, each containing a "Deactivate"
        # button. The first (top) "Deactivate" button is hidden, causing
        # `wait_for_visibility` to fail. To avoid this issue, we use
        # `wait_for='presence'` instead, ensuring we locat the elements regardless
        # of visibility. We then select the last (visible) button and click it.
        self.find_elements(
            by=By.CSS_SELECTOR,
            value='input.deletelink[type="submit"]',
            wait_for="presence",
        )[-1].click()
        device.refresh_from_db()
        config.refresh_from_db()
        self.assertEqual(device.is_deactivated(), True)
        self.assertEqual(config.is_deactivating(), True)

        self.open(
            reverse(f"admin:{self.config_app_label}_device_change", args=[device.id])
        )
        self.hide_loading_overlay()
        # Use `presence` instead of `visibility` for `wait_for`,
        # as the same issue described above applies here.
        self.find_elements(
            by=By.CSS_SELECTOR, value="a.deletelink", wait_for="presence"
        )[-1].click()
        self.wait_for_visibility(
            By.CSS_SELECTOR, "#deactivating-warning .messagelist .warning p"
        )
        self.find_element(by=By.CSS_SELECTOR, value="#warning-ack").click()
        # After accepting the warning, wee need to wait for the animation
        # to complete before trying to interact with the button,
        # otherwise the test may fail due to the button not being fully
        # visible or clickable yet.
        time.sleep(1)
        delete_confirm = self.find_element(
            By.CSS_SELECTOR, 'form[method="post"] input[type="submit"]'
        )
        delete_confirm.click()
        self.assertEqual(Device.objects.count(), 0)

    def test_force_delete_multiple_devices_with_deactivating_config(self):
        self._create_template(default=True)
        org = self._get_org()
        device1 = self._create_device(organization=org)
        config1 = self._create_config(device=device1)
        device2 = self._create_device(
            organization=org, name="test2", mac_address="22:22:22:22:22:22"
        )
        config2 = self._create_config(device=device2)
        self.assertEqual(device1.is_deactivated(), False)
        self.assertEqual(config1.status, "modified")
        self.assertEqual(device2.is_deactivated(), False)
        self.assertEqual(config2.status, "modified")

        self.login()
        self.open(reverse(f"admin:{self.config_app_label}_device_changelist"))
        self.find_element(by=By.CSS_SELECTOR, value="#action-toggle").click()
        select = Select(self.find_element(by=By.NAME, value="action"))
        select.select_by_value("delete_selected")
        self.find_element(
            by=By.CSS_SELECTOR, value='button[type="submit"][name="index"][value="0"]'
        ).click()
        self.wait_for_visibility(
            By.CSS_SELECTOR, "#deactivating-warning .messagelist .warning p"
        )
        self.find_element(by=By.CSS_SELECTOR, value="#warning-ack").click()
        # After accepting the warning, wee need to wait for the animation
        # to complete before trying to interact with the button,
        # otherwise the test may fail due to the button not being fully
        # visible or clickable yet.
        time.sleep(1)
        delete_confirm = self.find_element(
            By.CSS_SELECTOR, 'form[method="post"] input[type="submit"]'
        )
        delete_confirm.click()
        self.assertEqual(Device.objects.count(), 0)

    def test_add_remove_templates(self):
        template = self._create_template(organization=self._get_org())
        config = self._create_config(organization=self._get_org())
        device = config.device
        self.login()
        # some times the url fetching in js gives unauthorized error
        # so we add a wait to allow login to complete
        time.sleep(2)

        with self.subTest("Template should be added"):
            self._update_template(device.id, templates=[template])
            config.refresh_from_db()
            self.assertEqual(config.templates.count(), 1)
            self.assertEqual(config.status, "modified")
            config.set_status_applied()
            self.assertEqual(config.status, "applied")

        with self.subTest("Template should be removed"):
            self._update_template(device.id, templates=[template], is_enabled=True)
            config.refresh_from_db()
            self.assertEqual(config.templates.count(), 0)
            self.assertEqual(config.status, "modified")


@tag("selenium_tests")
class TestDeviceGroupAdmin(
    SeleniumTestMixin,
    CreateConfigTemplateMixin,
    StaticLiveServerTestCase,
):
    def test_show_relevant_templates(self):
        org1 = self._create_org(name="org1", slug="org1")
        org2 = self._create_org(name="org2", slug="org2")
        shared_template = self._create_template(name="shared template")
        org1_template = self._create_template(name="org1 template", organization=org1)
        org1_required_template = self._create_template(
            name="org1 required", organization=org1, required=True
        )
        org1_default_template = self._create_template(
            name="org1 default", organization=org1, default=True
        )
        org2_template = self._create_template(name="org2 template", organization=org2)
        org2_required_template = self._create_template(
            name="org2 required", organization=org2, required=True
        )
        org2_default_template = self._create_template(
            name="org2 default", organization=org2, default=True
        )

        self.login()
        self.open(reverse(f"admin:{self.config_app_label}_devicegroup_add"))
        self.assertEqual(
            self.wait_for_visibility(
                By.CSS_SELECTOR, ".sortedm2m-container .help"
            ).text,
            "No Template available",
        )
        self.find_element(by=By.CSS_SELECTOR, value='input[name="name"]').send_keys(
            "Test Device Group"
        )
        self._select_organization(org1)
        self._verify_templates_visibility(
            hidden=[
                org1_default_template,
                org1_required_template,
                org2_template,
                org2_default_template,
                org2_required_template,
            ],
            visible=[shared_template, org1_template],
        )
        # Select org1 template
        self.find_element(
            by=By.XPATH, value=f'//*[@value="{org1_template.id}"]'
        ).click()
        self.web_driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);"
        )
        self.find_element(by=By.CSS_SELECTOR, value='input[name="_continue"]').click()
        self._wait_until_page_ready()
        device_group = DeviceGroup.objects.first()
        self.assertEqual(device_group.name, "Test Device Group")
        self.assertIn(org1_template, device_group.templates.all())
        self.assertEqual(
            self.find_element(
                by=By.CSS_SELECTOR,
                value=f'input[type="checkbox"][value="{org1_template.id}"]',
            ).is_selected(),
            True,
        )

        with self.subTest("Change organization to org2"):
            self._select_organization(org2)
            self._verify_templates_visibility(
                hidden=[
                    org1_template,
                    org1_default_template,
                    org1_required_template,
                    org2_required_template,
                    org2_default_template,
                ],
                visible=[
                    shared_template,
                    org2_template,
                ],
            )
            self.assertEqual(
                self.find_element(
                    by=By.CSS_SELECTOR,
                    value=f'input[type="checkbox"][value="{org2_template.id}"]',
                ).is_selected(),
                False,
            )
            self.find_element(
                by=By.CSS_SELECTOR, value='input[name="_continue"]'
            ).click()
            self._wait_until_page_ready()
            self.assertEqual(device_group.templates.count(), 0)
            self.assertEqual(
                self.find_element(
                    by=By.CSS_SELECTOR,
                    value=f'input[type="checkbox"][value="{org2_template.id}"]',
                ).is_selected(),
                False,
            )


@tag("selenium_tests")
class TestDeviceAdminUnsavedChanges(
    SeleniumTestMixin,
    CreateConfigTemplateMixin,
    StaticLiveServerTestCase,
):
    browser = "chrome"

    @classmethod
    def get_chrome_webdriver(cls):
        """
        Override the parent class method to enable BiDi mode and set
        unhandledPromptBehavior to "ignore". This is required to test
        beforeunload alerts, as Chromium v126+ auto-accepts them per
        WebDriver standard.

        Ref: https://github.com/openwisp/openwisp-controller/issues/902
        """
        options = webdriver.ChromeOptions()
        options.page_load_strategy = "eager"
        if os.environ.get("SELENIUM_HEADLESS", False):
            options.add_argument("--headless")
        CHROME_BIN = os.environ.get("CHROME_BIN", None)
        if CHROME_BIN:
            options.binary_location = CHROME_BIN
        options.add_argument("--window-size=1366,768")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument(f"--remote-debugging-port={free_port()}")
        options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        # Enable BiDi mode and set unhandledPromptBehavior to "ignore"
        # to allow testing beforeunload alerts (Chromium v126+).
        options.enable_bidi = True
        options.set_capability("unhandledPromptBehavior", "ignore")
        return webdriver.Chrome(options=options)

    def _is_unsaved_changes_alert_present(self):
        for entry in self.get_browser_logs():
            if (
                entry["level"] == "WARNING"
                and "You haven't saved your changes yet!" in entry["message"]
            ):
                return True
        return False

    def _override_unsaved_changes_alert(self):
        self.web_driver.execute_script(
            'django.jQuery(window).on("beforeunload", function(e) {'
            " console.warn(e.returnValue); });"
        )

    def test_unsaved_changes(self):
        """
        Execute this test using Chrome instead of Firefox.
        Firefox automatically accepts the beforeunload alert, which makes it
        impossible to test the unsaved changes alert.
        """
        self.login()
        self._create_template(default=True, default_values={"ssid": "default"})
        device = self._create_config(organization=self._get_org()).device
        path = reverse(f"admin:{self.config_app_label}_device_change", args=[device.id])

        with self.subTest("Alert should not be displayed without any change"):
            self.open(path)
            self.hide_loading_overlay()
            self._override_unsaved_changes_alert()
            # Simulate navigating away from the page
            self.open(reverse("admin:index"))
            if self._is_unsaved_changes_alert_present():
                self.fail("Unsaved changes alert displayed without any change")

        with self.subTest("Alert should be displayed after making changes"):
            # The WebDriver automatically accepts the
            # beforeunload confirmation dialog. To verify the message,
            # we log it to the console and check its content.
            #
            # our own JS code sets e.returnValue when triggered
            # so we just need to ensure it's set as expected
            self.open(path)
            self.hide_loading_overlay()
            self._override_unsaved_changes_alert()
            # simulate hand gestures
            self.find_element(by=By.TAG_NAME, value="body").click()
            self.find_element(by=By.NAME, value="name").click()
            # set name
            self.find_element(by=By.NAME, value="name").send_keys("new.device.name")
            # simulate hand gestures
            self.find_element(by=By.TAG_NAME, value="body").click()
            self.web_driver.refresh()
            if not self._is_unsaved_changes_alert_present():
                self.fail("Unsaved changes code was not executed.")

    def test_template_context_variables(self):
        self._create_template(
            name="Template1", default_values={"vni": "1"}, required=True
        )
        self._create_template(
            name="Template2", default_values={"vni": "2"}, required=True
        )
        device = self._create_config(organization=self._get_org()).device
        self.login()
        self.open(
            reverse(f"admin:{self.config_app_label}_device_change", args=[device.id])
            + "#config-group"
        )
        self.hide_loading_overlay()
        try:
            WebDriverWait(self.web_driver, 2).until(
                EC.text_to_be_present_in_element_value(
                    (
                        By.XPATH,
                        '//*[@id="flat-json-config-0-context"]/div[2]/div/div/input[1]',
                    ),
                    "vni",
                )
            )
        except TimeoutException:
            self.fail("Timed out waiting for configuration variables to get loaded")

        with self.subTest("Navigating away from the page should not show alert"):
            self._override_unsaved_changes_alert()
            # Simulate navigating away from the page
            self.find_element(
                by=By.XPATH, value='//*[@id="main-content"]/div[2]/a[3]'
            ).click()
            if self._is_unsaved_changes_alert_present():
                self.fail("Unsaved changes alert displayed without any change")

        with self.subTest("Saving the objects should not save context variables"):
            self.open(
                reverse(
                    f"admin:{self.config_app_label}_device_change", args=[device.id]
                )
            )
            self.web_driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            self.find_element(
                by=By.CSS_SELECTOR, value='input[name="_continue"]'
            ).click()
            device.refresh_from_db()
            self.assertEqual(device.config.context, {})


@tag("selenium_tests")
class TestVpnAdmin(
    SeleniumTestMixin,
    CreateConfigTemplateMixin,
    TestWireguardVpnMixin,
    StaticLiveServerTestCase,
):
    def test_vpn_edit(self):
        self.login()
        device, vpn, template = self._create_wireguard_vpn_template()
        self.open(reverse(f"admin:{self.config_app_label}_vpn_change", args=[vpn.id]))
        with self.subTest("Ca and Cert should not be visible"):
            self.wait_for_invisibility(by=By.CLASS_NAME, value="field-ca")
            self.wait_for_invisibility(by=By.CLASS_NAME, value="field-cert")

        with self.subTest("PrivateKey is shown in configuration preview"):
            self.find_element(by=By.CSS_SELECTOR, value=".previewlink").click()
            self.wait_for_visibility(By.CSS_SELECTOR, ".djnjc-preformatted")
            self.assertIn(
                f"PrivateKey = {vpn.private_key}",
                self.find_element(by=By.CSS_SELECTOR, value=".djnjc-preformatted").text,
            )
        # Close the configuration preview
        self.find_element(by=By.CSS_SELECTOR, value=".djnjc-overlay a.close").click()

        with self.subTest("Changing VPN backend should hide webhook and authtoken"):
            backend = Select(self.find_element(by=By.ID, value="id_backend"))
            backend.select_by_visible_text("OpenVPN")
            self.wait_for_invisibility(by=By.CLASS_NAME, value="field-webhook_endpoint")
            self.wait_for_invisibility(by=By.CLASS_NAME, value="field-auth_token")
