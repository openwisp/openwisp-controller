from django.contrib.auth.models import Permission
from django.test import tag
from django.urls import reverse
from selenium.webdriver.support.ui import Select
from swapper import load_model

from ...tests.utils import MultitenantSeleniumTestCase

Group = load_model('openwisp_users', 'Group')


@tag('selenium')
class TestMultitenantAdmin(MultitenantSeleniumTestCase):
    app_label = 'connection'
    serialized_rollback = True

    def open(self, url, driver=None):
        super().open(url, driver)
        connector_select = Select(self.web_driver.find_element_by_id('id_connector'))
        connector_select.select_by_visible_text('SSH')

    def test_credentials_multitenant_organization(self):
        group = Group.objects.get(name='Administrator')
        group.permissions.add(
            *Permission.objects.filter(codename__endswith='credentials')
        )
        url = reverse(f'admin:{self.app_label}_credentials_add')
        self._test_organization_field_multitenancy(url)
