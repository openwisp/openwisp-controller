from django.contrib.auth import get_user_model
from django.urls import reverse

from openwisp_users.tests.utils import TestMultitenantAdminMixin

user_model = get_user_model()


class TestAdminMixin(TestMultitenantAdminMixin):
    def _test_changelist_recover_deleted(self, app_label, model_label):
        self._test_multitenant_admin(
            url=reverse('admin:{0}_{1}_changelist'.format(app_label, model_label)),
            visible=[],
            hidden=[],
        )

    def _login(self, username='admin', password='tester'):
        self.client.force_login(user_model.objects.get(username=username))


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
            driver.find_element_by_name('username').send_keys(username)
            driver.find_element_by_name('password').send_keys(password)
            driver.find_element_by_xpath('//input[@type="submit"]').click()
