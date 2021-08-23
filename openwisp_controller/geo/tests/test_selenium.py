from django.contrib.auth.models import Permission
from django.test import tag
from django.urls import reverse
from swapper import load_model

from ...tests.utils import MultitenantSeleniumTestCase

Group = load_model('openwisp_users', 'Group')


@tag('selenium')
class TestMultitenantAdmin(MultitenantSeleniumTestCase):
    app_label = 'geo'
    serialized_rollback = True

    def test_location_multitenant_organization(self):
        group = Group.objects.get(name='Administrator')
        group.permissions.add(*Permission.objects.filter(codename__endswith='location'))
        url = reverse(f'admin:{self.app_label}_location_add')
        self._test_organization_field_multitenancy(url)
