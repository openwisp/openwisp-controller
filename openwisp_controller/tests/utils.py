from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    UnexpectedAlertPresentException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from swapper import load_model

from openwisp_users.tests.utils import TestMultitenantAdminMixin, TestOrganizationMixin

Group = load_model('openwisp_users', 'Group')

user_model = get_user_model()


class TestAdminMixin(TestMultitenantAdminMixin):
    def _login(self, username='admin', password='tester'):
        self.client.force_login(user_model.objects.get(username=username))


class SeleniumTestCase(StaticLiveServerTestCase):
    """
    A base test case for Selenium, providing helped methods for generating
    clients and logging in profiles.
    """

    admin_username = 'admin'
    admin_password = 'password'

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
            driver.find_element_by_name('username').send_keys(username)
            driver.find_element_by_name('password').send_keys(password)
            driver.find_element_by_xpath('//input[@type="submit"]').click()

    def logout(self, driver=None):
        if not driver:
            driver = self.web_driver
        driver.get(f'{self.live_server_url}/admin/logout/')

    def accept_unsaved_changes_alert(self):
        # Accept unsaved changes alert to allow other tests to run
        try:
            self.web_driver.refresh()
        except UnexpectedAlertPresentException:
            self.web_driver.switch_to_alert().accept()
        else:
            try:
                WebDriverWait(self.web_driver, 1).until(EC.alert_is_present())
            except TimeoutException:
                pass
            else:
                self.web_driver.switch_to_alert().accept()
        self.web_driver.refresh()
        WebDriverWait(self.web_driver, 2).until(
            EC.visibility_of_element_located((By.XPATH, '//*[@id="site-name"]'))
        )

    def tearDown(self):
        self.accept_unsaved_changes_alert()


class MultitenantSeleniumTestCase(TestOrganizationMixin, SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self.superuser = self._create_admin(
            username='superuser', password=self.admin_password, first_name='Superuser'
        )
        self.org1 = self._create_org(name='test1org')
        self.org2 = self._create_org(name='test2org')
        self.inactive_org = self._create_org(name='inactive-org', is_active=False)
        self.administrator_accessible_orgs = [self.org1]
        self.administrator_inaccessible_orgs = [self.org2, self.inactive_org]
        self.administrator = self._create_user(
            is_staff=True,
            username=self.admin_username,
            password=self.admin_password,
            email='administrator@example.com',
            first_name='Administrator',
        )
        self._create_org_user(
            is_admin=True, organization=self.org1, user=self.administrator
        )
        self._create_org_user(
            is_admin=True, organization=self.inactive_org, user=self.administrator
        )
        self.administrator.groups.add(Group.objects.get(name='Administrator'))

    def _test_organization_field_multitenancy(self, url):
        def _test_for_accessible_org(org):
            self.web_driver.find_element_by_css_selector(
                'span[data-select2-id="1"]'
            ).click()
            self.web_driver.find_element_by_css_selector(
                'input.select2-search__field'
            ).send_keys(org.name)
            try:
                WebDriverWait(self.web_driver, 1).until(
                    EC.text_to_be_present_in_element(
                        (By.XPATH, '//*[@id="select2-id_organization-results"]/li',),
                        org.name,
                    )
                )
            except TimeoutException:
                self.fail(f'Timed out wating for {org} option')

            # Clear select2 search field
            self.web_driver.find_element_by_css_selector(
                'span[data-select2-id="1"]'
            ).click()

        def _test_for_inaccessible_org(org):
            self.web_driver.find_element_by_css_selector(
                'span[data-select2-id="1"]'
            ).click()
            self.web_driver.find_element_by_css_selector(
                'input.select2-search__field'
            ).send_keys(org.name)
            try:
                WebDriverWait(self.web_driver, 1).until(
                    EC.text_to_be_present_in_element(
                        (By.XPATH, '//*[@id="select2-id_organization-results"]/li',),
                        org.name,
                    )
                )
            except (TimeoutException, NoSuchElementException):
                # Expected behavior
                pass
            else:
                self.fail(f'Administrator is able to select {org} without membership')

            # Clear select2 search field
            self.web_driver.find_element_by_css_selector(
                'span[data-select2-id="1"]'
            ).click()

        self.login(username=self.administrator.username, password=self.admin_password)
        self.open(url)
        for org in self.administrator_accessible_orgs:
            _test_for_accessible_org(org)

        # Administrator should not be able to select non member organization
        for org in self.administrator_inaccessible_orgs:
            _test_for_inaccessible_org(org)

        self.accept_unsaved_changes_alert()
        self.logout()
        self.login(username=self.superuser.username, password=self.admin_password)
        self.open(url)
        # Superuser should be able to select all organizations
        for org in (
            self.administrator_accessible_orgs + self.administrator_inaccessible_orgs
        ):
            _test_for_accessible_org(org)
