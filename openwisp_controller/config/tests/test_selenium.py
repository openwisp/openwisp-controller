from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls.base import reverse
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    UnexpectedAlertPresentException,
)
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from openwisp_utils.test_selenium_mixins import SeleniumTestMixin

from .utils import CreateConfigTemplateMixin, TestWireguardVpnMixin


class SeleniumBaseMixin(CreateConfigTemplateMixin, SeleniumTestMixin):
    def setUp(self):
        self.admin = self._create_admin(
            username=self.admin_username, password=self.admin_password
        )


@tag('selenium_tests')
class TestDeviceAdmin(
    SeleniumBaseMixin,
    StaticLiveServerTestCase,
):
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

    def test_create_new_device(self):
        required_template = self._create_template(name='Required', required=True)
        default_template = self._create_template(name='Default', default=True)
        org = self._get_org()
        self.login()
        self.open(reverse('admin:config_device_add'))
        self.web_driver.find_element(by=By.NAME, value='name').send_keys(
            '11:22:33:44:55:66'
        )
        self.web_driver.find_element(
            by=By.CSS_SELECTOR, value='#select2-id_organization-container'
        ).click()
        WebDriverWait(self.web_driver, 2).until(
            EC.invisibility_of_element_located(
                (By.CSS_SELECTOR, '.select2-results__option.loading-results')
            )
        )
        self.web_driver.find_element(
            by=By.CLASS_NAME, value='select2-search__field'
        ).send_keys(org.name)
        WebDriverWait(self.web_driver, 2).until(
            EC.invisibility_of_element_located(
                (By.CSS_SELECTOR, '.select2-results__option.loading-results')
            )
        )
        self.web_driver.find_element(
            by=By.CLASS_NAME, value='select2-results__option'
        ).click()
        self.web_driver.find_element(by=By.NAME, value='mac_address').send_keys(
            '11:22:33:44:55:66'
        )
        self.web_driver.find_element(
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
        required_template_element = self.web_driver.find_element(
            by=By.XPATH, value=f'//*[@value="{required_template.id}"]'
        )
        default_template_element = self.web_driver.find_element(
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
        self.web_driver.find_element(by=By.NAME, value='_save').click()
        try:
            WebDriverWait(self.web_driver, 5).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '.messagelist .success')
                )
            )
        except TimeoutException:
            self.fail('Device added success message timed out')
        self.assertEqual(
            self.web_driver.find_elements(by=By.CLASS_NAME, value='success')[0].text,
            'The Device “11:22:33:44:55:66” was added successfully.',
        )

    def test_unsaved_changes(self):
        self.login()
        device = self._create_config(organization=self._get_org()).device
        self.open(reverse('admin:config_device_change', args=[device.id]))
        with self.subTest('Alert should not be displayed without any change'):
            self.web_driver.refresh()
            try:
                WebDriverWait(self.web_driver, 1).until(EC.alert_is_present())
            except TimeoutException:
                pass
            else:
                self.fail('Unsaved changes alert displayed without any change')

        with self.subTest('Alert should be displayed after making changes'):
            # simulate hand gestures
            self.web_driver.find_element(by=By.TAG_NAME, value='body').click()
            self.web_driver.find_element(by=By.NAME, value='name').click()
            # set name
            self.web_driver.find_element(by=By.NAME, value='name').send_keys(
                'new.device.name'
            )
            # simulate hand gestures
            self.web_driver.find_element(by=By.TAG_NAME, value='body').click()
            self.web_driver.refresh()
            try:
                WebDriverWait(self.web_driver, 1).until(EC.alert_is_present())
            except TimeoutException:
                for entry in self.web_driver.get_log('browser'):
                    print(entry)
                self.fail('Timed out wating for unsaved changes alert')
            else:
                alert = Alert(self.web_driver)
                alert.accept()

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
        wait = WebDriverWait(self.web_driver, 2)
        # org2 templates should not be visible
        try:
            wait.until(
                EC.invisibility_of_element_located(
                    (By.XPATH, f'//*[@value="{org2_required_template.id}"]')
                )
            )
            wait.until(
                EC.invisibility_of_element_located(
                    (By.XPATH, f'//*[@value="{org2_default_template.id}"]')
                )
            )
        except (TimeoutException, StaleElementReferenceException):
            self.fail('Template belonging to other organization found')

        # org1 and shared templates should be visible
        wait.until(
            EC.visibility_of_any_elements_located(
                (By.XPATH, f'//*[@value="{org1_required_template.id}"]')
            )
        )
        wait.until(
            EC.visibility_of_any_elements_located(
                (By.XPATH, f'//*[@value="{org1_default_template.id}"]')
            )
        )
        wait.until(
            EC.visibility_of_any_elements_located(
                (By.XPATH, f'//*[@value="{shared_required_template.id}"]')
            )
        )

    def test_change_config_backend(self):
        device = self._create_config(organization=self._get_org()).device
        template = self._create_template()

        self.login()
        self.open(
            reverse('admin:config_device_change', args=[device.id]) + '#config-group'
        )
        self.web_driver.find_element(by=By.XPATH, value=f'//*[@value="{template.id}"]')
        # Change config backed to
        config_backend_select = Select(
            self.web_driver.find_element(by=By.NAME, value='config-0-backend')
        )
        config_backend_select.select_by_visible_text('OpenWISP Firmware 1.x')
        try:
            WebDriverWait(self.web_driver, 1).until(
                EC.invisibility_of_element_located(
                    (By.XPATH, f'//*[@value="{template.id}"]')
                )
            )
        except TimeoutException:
            self.fail('Template for other config backend found')

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
        self.web_driver.find_element(
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


class TestVpnAdmin(SeleniumBaseMixin, TestWireguardVpnMixin, StaticLiveServerTestCase):
    def test_vpn_edit(self):
        self.login()
        device, vpn, template = self._create_wireguard_vpn_template()
        self.open(reverse('admin:config_vpn_change', args=[vpn.id]))
        with self.subTest('Ca and Cert should not be visible'):
            el = self.web_driver.find_element(by=By.CLASS_NAME, value='field-ca')
            self.assertFalse(el.is_displayed())
            el = self.web_driver.find_element(by=By.CLASS_NAME, value='field-cert')
            self.assertFalse(el.is_displayed())

        with self.subTest('PrivateKey is shown in configuration preview'):
            self.web_driver.find_element(
                by=By.CSS_SELECTOR, value='.previewlink'
            ).click()
            WebDriverWait(self.web_driver, 2).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, '.djnjc-preformatted')
                )
            )
            self.assertIn(
                f'PrivateKey = {vpn.private_key}',
                self.web_driver.find_element(
                    by=By.CSS_SELECTOR, value='.djnjc-preformatted'
                ).text,
            )
        # Close the configuration preview
        self.web_driver.find_element(
            by=By.CSS_SELECTOR, value='.djnjc-overlay a.close'
        ).click()

        with self.subTest('Changing VPN backend should hide webhook and authtoken'):
            backend = Select(self.web_driver.find_element(by=By.ID, value='id_backend'))
            backend.select_by_visible_text('OpenVPN')
            el = self.web_driver.find_element(
                by=By.CLASS_NAME, value='field-webhook_endpoint'
            )
            self.assertFalse(el.is_displayed())
            el = self.web_driver.find_element(
                by=By.CLASS_NAME, value='field-auth_token'
            )
            self.assertFalse(el.is_displayed())
