import time

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls.base import reverse
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from swapper import load_model

from openwisp_utils.tests import SeleniumTestMixin

from .utils import CreateConfigTemplateMixin, TestWireguardVpnMixin

Device = load_model('config', 'Device')


@tag('selenium_tests')
class TestDeviceAdmin(
    SeleniumTestMixin,
    CreateConfigTemplateMixin,
    StaticLiveServerTestCase,
):
    def test_create_new_device(self):
        required_template = self._create_template(name='Required', required=True)
        default_template = self._create_template(name='Default', default=True)
        org = self._get_org()
        self.login()
        self.open(reverse('admin:config_device_add'))
        self.find_element(by=By.NAME, value='name').send_keys('11:22:33:44:55:66')
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
        self.find_element(by=By.NAME, value='mac_address').send_keys(
            '11:22:33:44:55:66'
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
                    f'{required_template.id},{default_template.id}',
                )
            )
        except TimeoutException:
            self.fail('Relevant templates logic was not executed')
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
        self.find_element(by=By.NAME, value='_save').click()
        self.wait_for_presence(By.CSS_SELECTOR, '.messagelist .success')
        self.assertEqual(
            self.find_elements(by=By.CLASS_NAME, value='success')[0].text,
            'The Device “11:22:33:44:55:66” was added successfully.',
        )

    def test_device_preview_keyboard_shortcuts(self):
        device = self._create_config(device=self._create_device(name='Test')).device
        self.login()
        self.open(reverse('admin:config_device_changelist'))
        try:
            self.open(reverse('admin:config_device_change', args=[device.id]))
            self.hide_loading_overlay()
        except TimeoutException:
            self.fail('Device detail page did not load in time')

        with self.subTest('press ALT + P and expect overlay to be shown'):
            actions = ActionChains(self.web_driver)
            actions.key_down(Keys.ALT).send_keys('p').key_up(Keys.ALT).perform()
            self.wait_for_visibility(By.CSS_SELECTOR, '.djnjc-overlay:not(.loading)')

        with self.subTest('press ESC to close preview overlay'):
            actions = ActionChains(self.web_driver)
            actions.send_keys(Keys.ESCAPE).perform()
            self.wait_for_invisibility(By.CSS_SELECTOR, '.djnjc-overlay:not(.loading)')

    def test_multiple_organization_templates(self):
        shared_required_template = self._create_template(
            name='shared required', organization=None
        )

        org1 = self._create_org(name='org1', slug='org1')
        org1_required_template = self._create_template(
            name='org1 required', organization=org1, required=True
        )
        org1_default_template = self._create_template(
            name='org1 default', organization=org1, default=True
        )

        org2 = self._create_org(name='org2', slug='org2')
        org2_required_template = self._create_template(
            name='org2 required', organization=org2, required=True
        )
        org2_default_template = self._create_template(
            name='org2 default', organization=org2, default=True
        )

        org1_device = self._create_config(
            device=self._create_device(organization=org1)
        ).device

        self.login()
        self.open(
            reverse('admin:config_device_change', args=[org1_device.id])
            + '#config-group'
        )
        self.hide_loading_overlay()
        # org2 templates should not be visible
        self.wait_for_invisibility(
            By.XPATH, f'//*[@value="{org2_required_template.id}"]'
        )
        self.wait_for_invisibility(
            By.XPATH, f'//*[@value="{org2_default_template.id}"]'
        )

        # org1 and shared templates should be visible
        self.wait_for_visibility(By.XPATH, f'//*[@value="{org1_required_template.id}"]')
        self.wait_for_visibility(By.XPATH, f'//*[@value="{org1_default_template.id}"]')
        self.wait_for_visibility(
            By.XPATH, f'//*[@value="{shared_required_template.id}"]'
        )

    def test_change_config_backend(self):
        device = self._create_config(organization=self._get_org()).device
        template = self._create_template()

        self.login()
        self.open(
            reverse('admin:config_device_change', args=[device.id]) + '#config-group'
        )
        self.hide_loading_overlay()
        self.find_element(by=By.XPATH, value=f'//*[@value="{template.id}"]')
        # Change config backed to
        config_backend_select = Select(
            self.find_element(by=By.NAME, value='config-0-backend')
        )
        config_backend_select.select_by_visible_text('OpenWISP Firmware 1.x')
        self.wait_for_invisibility(By.XPATH, f'//*[@value="{template.id}"]')

    def test_template_context_variables(self):
        self._create_template(
            name='Template1', default_values={'vni': '1'}, required=True
        )
        self._create_template(
            name='Template2', default_values={'vni': '2'}, required=True
        )
        device = self._create_config(organization=self._get_org()).device
        self.login()
        self.open(
            reverse('admin:config_device_change', args=[device.id]) + '#config-group'
        )
        self.hide_loading_overlay()
        try:
            WebDriverWait(self.web_driver, 2).until(
                EC.text_to_be_present_in_element_value(
                    (
                        By.XPATH,
                        '//*[@id="flat-json-config-0-context"]/div[2]/div/div/input[1]',
                    ),
                    'vni',
                )
            )
        except TimeoutException:
            self.fail('Timed out wating for configuration variabled to get loaded')
        self.find_element(
            by=By.XPATH, value='//*[@id="main-content"]/div[2]/a[3]'
        ).click()
        try:
            WebDriverWait(self.web_driver, 2).until(EC.alert_is_present())
        except TimeoutException:
            pass
        else:
            alert = Alert(self.web_driver)
            alert.accept()
            self.fail('Unsaved changes alert displayed without any change')

    def test_force_delete_device_with_deactivating_config(self):
        self._create_template(default=True)
        config = self._create_config(organization=self._get_org())
        device = config.device
        self.assertEqual(device.is_deactivated(), False)
        self.assertEqual(config.status, 'modified')

        self.login()
        self.open(reverse('admin:config_device_change', args=[device.id]))
        self.hide_loading_overlay()
        # The webpage has two "submit-row" sections, each containing a "Deactivate"
        # button. The first (top) "Deactivate" button is hidden, causing
        # `wait_for_visibility` to fail. To avoid this issue, we use
        # `wait_for='presence'` instead, ensuring we locat the elements regardless
        # of visibility. We then select the last (visible) button and click it.
        self.find_elements(
            by=By.CSS_SELECTOR,
            value='input.deletelink[type="submit"]',
            wait_for='presence',
        )[-1].click()
        device.refresh_from_db()
        config.refresh_from_db()
        self.assertEqual(device.is_deactivated(), True)
        self.assertEqual(config.is_deactivating(), True)

        self.open(reverse('admin:config_device_change', args=[device.id]))
        self.hide_loading_overlay()
        # Use `presence` instead of `visibility` for `wait_for`,
        # as the same issue described above applies here.
        self.find_elements(
            by=By.CSS_SELECTOR, value='a.deletelink', wait_for='presence'
        )[-1].click()
        self.wait_for_visibility(
            By.CSS_SELECTOR, '#deactivating-warning .messagelist .warning p'
        )
        self.find_element(by=By.CSS_SELECTOR, value='#warning-ack').click()
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
            organization=org, name='test2', mac_address='22:22:22:22:22:22'
        )
        config2 = self._create_config(device=device2)
        self.assertEqual(device1.is_deactivated(), False)
        self.assertEqual(config1.status, 'modified')
        self.assertEqual(device2.is_deactivated(), False)
        self.assertEqual(config2.status, 'modified')

        self.login()
        self.open(reverse('admin:config_device_changelist'))
        self.find_element(by=By.CSS_SELECTOR, value='#action-toggle').click()
        select = Select(self.find_element(by=By.NAME, value='action'))
        select.select_by_value('delete_selected')
        self.find_element(
            by=By.CSS_SELECTOR, value='button[type="submit"][name="index"][value="0"]'
        ).click()
        self.wait_for_visibility(
            By.CSS_SELECTOR, '#deactivating-warning .messagelist .warning p'
        )
        self.find_element(by=By.CSS_SELECTOR, value='#warning-ack').click()
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


@tag('selenium_tests')
class TestDeviceAdminUnsavedChanges(
    SeleniumTestMixin,
    CreateConfigTemplateMixin,
    StaticLiveServerTestCase,
):
    browser = 'chrome'

    def test_unsaved_changes(self):
        """
        Execute this test using Chrome instead of Firefox.
        Firefox automatically accepts the beforeunload alert, which makes it
        impossible to test the unsaved changes alert.
        """
        self.login()
        device = self._create_config(organization=self._get_org()).device
        path = reverse('admin:config_device_change', args=[device.id])

        with self.subTest('Alert should not be displayed without any change'):
            self.open(path)
            self.hide_loading_overlay()
            try:
                WebDriverWait(self.web_driver, 1).until(EC.alert_is_present())
            except TimeoutException:
                pass
            else:
                self.fail('Unsaved changes alert displayed without any change')

        with self.subTest('Alert should be displayed after making changes'):
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
            # simulate hand gestures
            self.find_element(by=By.TAG_NAME, value='body').click()
            self.find_element(by=By.NAME, value='name').click()
            # set name
            self.find_element(by=By.NAME, value='name').send_keys('new.device.name')
            # simulate hand gestures
            self.find_element(by=By.TAG_NAME, value='body').click()
            self.web_driver.refresh()
            for entry in self.get_browser_logs():
                if (
                    entry['level'] == 'WARNING'
                    and "You haven\'t saved your changes yet!" in entry['message']
                ):
                    break
            else:
                self.fail('Unsaved changes code was not executed.')


@tag('selenium_tests')
class TestVpnAdmin(
    SeleniumTestMixin,
    CreateConfigTemplateMixin,
    TestWireguardVpnMixin,
    StaticLiveServerTestCase,
):
    def test_vpn_edit(self):
        self.login()
        device, vpn, template = self._create_wireguard_vpn_template()
        self.open(reverse('admin:config_vpn_change', args=[vpn.id]))
        with self.subTest('Ca and Cert should not be visible'):
            self.wait_for_invisibility(by=By.CLASS_NAME, value='field-ca')
            self.wait_for_invisibility(by=By.CLASS_NAME, value='field-cert')

        with self.subTest('PrivateKey is shown in configuration preview'):
            self.find_element(by=By.CSS_SELECTOR, value='.previewlink').click()
            self.wait_for_visibility(By.CSS_SELECTOR, '.djnjc-preformatted')
            self.assertIn(
                f'PrivateKey = {vpn.private_key}',
                self.find_element(by=By.CSS_SELECTOR, value='.djnjc-preformatted').text,
            )
        # Close the configuration preview
        self.find_element(by=By.CSS_SELECTOR, value='.djnjc-overlay a.close').click()

        with self.subTest('Changing VPN backend should hide webhook and authtoken'):
            backend = Select(self.find_element(by=By.ID, value='id_backend'))
            backend.select_by_visible_text('OpenVPN')
            self.wait_for_invisibility(by=By.CLASS_NAME, value='field-webhook_endpoint')
            self.wait_for_invisibility(by=By.CLASS_NAME, value='field-auth_token')
