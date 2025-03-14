import django
from django.contrib.auth import get_user_model
from django.db import connections
from django.db.utils import DEFAULT_DB_ALIAS
from django.test.testcases import _AssertNumQueriesContext
from django.urls import reverse
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from openwisp_users.tests.utils import TestMultitenantAdminMixin
from openwisp_utils.test_selenium_mixins import SeleniumTestMixin

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


class _ManagementTransactionNumQueriesContext(_AssertNumQueriesContext):
    def __exit__(self, exc_type, exc_value, traceback):
        """
        Django 4.2 introduced support for logging transaction
        management queries (BEGIN, COMMIT, and ROLLBACK).
        This method increases the number of expected database
        queries if COMMIT/ROLLBACK queries are found when
        using Django 4.2
        """
        if exc_type is not None:
            return
        for query in self.captured_queries:
            if django.VERSION > (4, 2) and 'COMMIT' in query['sql']:
                self.num += 1
        super().__exit__(exc_type, exc_value, traceback)


class TransactionTestMixin(object):
    def assertNumQueries(self, num, func=None, *args, using=DEFAULT_DB_ALIAS, **kwargs):
        conn = connections[using]

        context = _ManagementTransactionNumQueriesContext(self, num, conn)
        if func is None:
            return context

        with context:
            func(*args, **kwargs)


class DeviceAdminSeleniumTextMixin(SeleniumTestMixin):
    def tearDown(self):
        super().tearDown()
        # Dismiss any unsaved changes alert to prevent it from blocking
        # navigation in subsequent tests. If left unresolved, this could
        # cause test failures by preventing the browser from loading new pages.
        # Ensuring a clean browser state before the next test runs.
        try:
            self.web_driver.refresh()
        except UnexpectedAlertPresentException:
            self.web_driver.switch_to_alert().accept()
            self.web_driver.switch_to_alert.accept()
        else:
            try:
                WebDriverWait(self.web_driver, 1).until(EC.alert_is_present())
            except TimeoutException:
                pass
            else:
                self.web_driver.switch_to_alert().accept()
        self.web_driver.refresh()
        self.wait_for_visibility(By.XPATH, '//*[@id="site-name"]')

    def open(self, url, driver=None):
        super().open(url, driver)
        driver = driver or self.web_driver
        self._assert_loading_overlay_hidden()

    def _assert_loading_overlay_hidden(self):
        self.wait_for_invisibility(By.CSS_SELECTOR, '#loading-overlay')
