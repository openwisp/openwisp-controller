from django.contrib.auth.models import Permission
from django.test import tag
from django.urls import reverse
from selenium.webdriver.support.ui import Select
from swapper import load_model

from ...tests.utils import MultitenantSeleniumTestCase

Group = load_model('openwisp_users', 'Group')


@tag('selenium')
class TestMultitenantAdmin(MultitenantSeleniumTestCase):
    app_label = 'pki'
    serialized_rollback = True

    def open(self, url, driver=None):
        super().open(url, driver)
        operation_select = Select(
            self.web_driver.find_element_by_id('id_operation_type')
        )
        operation_select.select_by_visible_text('Import Existing')

    def test_cert_multitenant_organization(self):
        group = Group.objects.get(name='Administrator')
        group.permissions.add(*Permission.objects.filter(codename__endswith='cert'))
        url = reverse(f'admin:{self.app_label}_cert_add')
        self._test_organization_field_multitenancy(url)
