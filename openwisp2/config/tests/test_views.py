from django.test import TestCase
from django.urls import reverse

from . import CreateAdminMixin, CreateConfigTemplateMixin
from ...tests import TestOrganizationMixin
from ..models import Template


class TestTemplate(CreateConfigTemplateMixin, CreateAdminMixin,
                   TestOrganizationMixin, TestCase):
    template_model = Template

    def _create_template_test_data(self):
        org1 = self._create_org(name='org1')
        org2 = self._create_org(name='org2')
        t1 = self._create_template(organization=org1, name='t1', default=True)
        t2 = self._create_template(organization=org2, name='t2', default=True)
        # shared template
        t3 = self._create_template(organization=None, name='t3', default=True)
        return org1, org2, t1, t2, t3

    def test_get_default_templates(self):
        org1, org2, t1, t2, t3 = self._create_template_test_data()
        self._login()
        response = self.client.get(reverse('config:get_default_templates',
                                           args=[org1.pk]))
        templates = response.json()['default_templates']
        self.assertEqual(len(templates), 2)
        self.assertIn(str(t1.pk), templates)
        self.assertIn(str(t3.pk), templates)
        response = self.client.get(reverse('config:get_default_templates',
                                           args=[org2.pk]))
        templates = response.json()['default_templates']
        self.assertEqual(len(templates), 2)
        self.assertIn(str(t2.pk), templates)
        self.assertIn(str(t3.pk), templates)

    def test_get_default_templates_403(self):
        org1 = self._create_org(name='org1')
        response = self.client.get(reverse('config:get_default_templates',
                                           args=[org1.pk]))
        self.assertEqual(response.status_code, 403)

    def test_get_default_templates_404(self):
        self._login()
        response = self.client.get(reverse('config:get_default_templates',
                                           args=['d80a60a1415e4836b8f4bc588b084c29']))
        self.assertEqual(response.status_code, 404)

    def test_get_default_templates_400(self):
        self._login()
        response = self.client.get(reverse('config:get_default_templates',
                                           args=['wrong']))
        self.assertEqual(response.status_code, 404)
