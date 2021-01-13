from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin

from ...tests.utils import TestAdminMixin
from .utils import CreateConfigTemplateMixin

Template = load_model('config', 'Template')
User = get_user_model()


class TestViews(
    CreateConfigTemplateMixin, TestAdminMixin, TestOrganizationMixin, TestCase
):
    """
    tests for config.views
    """

    def setUp(self):
        User.objects.create_superuser(
            username='admin', password='tester', email='admin@admin.com'
        )

    def test_schema_403(self):
        response = self.client.get(reverse('config:schema'))
        self.assertEqual(response.status_code, 403)
        self.assertIn('error', response.json())

    def test_schema_200(self):
        self.client.force_login(User.objects.get(username='admin'))
        response = self.client.get(reverse('config:schema'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('netjsonconfig.OpenWrt', response.json())

    def test_schema_hostname_hidden(self):
        from ..views import available_schemas

        for key, schema in available_schemas.items():
            if 'general' not in schema['properties']:
                continue
            if 'hostname' in schema['properties']['general']['properties']:
                self.fail('hostname property must be hidden')

    def _create_template_test_data(self):
        org1 = self._create_org(name='org1')
        org2 = self._create_org(name='org2')
        t1 = self._create_template(organization=org1, name='t1', default=True)
        t2 = self._create_template(organization=org2, name='t2', default=True)
        # shared template
        t3 = self._create_template(organization=None, name='t3', default=True)
        # inactive org and template
        inactive_org = self._create_org(name='inactive-org', is_active=False)
        inactive_t = self._create_template(
            organization=inactive_org, name='inactive-t', default=True
        )
        return org1, org2, t1, t2, t3, inactive_org, inactive_t

    def test_get_default_templates(self):
        (
            org1,
            org2,
            t1,
            t2,
            t3,
            inactive_org,
            inactive_t,
        ) = self._create_template_test_data()
        self._login()
        response = self.client.get(
            reverse('admin:get_default_templates', args=[org1.pk])
        )
        templates = response.json()['default_templates']
        self.assertEqual(len(templates), 2)
        self.assertIn(str(t1.pk), templates)
        self.assertIn(str(t3.pk), templates)
        response = self.client.get(
            reverse('admin:get_default_templates', args=[org2.pk])
        )
        templates = response.json()['default_templates']
        self.assertEqual(len(templates), 2)
        self.assertIn(str(t2.pk), templates)
        self.assertIn(str(t3.pk), templates)

    def test_get_default_templates_with_backend_filtering(self):
        org1 = self._create_org(name='org1')
        t1 = self._create_template(
            name='t1', organization=org1, default=True, backend='netjsonconfig.OpenWrt'
        )
        t2 = self._create_template(
            name='t2', organization=org1, default=True, backend='netjsonconfig.OpenWisp'
        )
        self._login()

        r = self.client.get(
            reverse('admin:get_default_templates', args=[org1.pk]),
            {'backend': 'netjsonconfig.OpenWrt'},
        )
        templates = r.json()['default_templates']
        self.assertEqual(len(templates), 1)
        self.assertIn(str(t1.pk), templates)
        self.assertNotIn(str(t2.pk), templates)

    def test_get_default_templates_403(self):
        org1 = self._create_org(name='org1')
        response = self.client.get(
            reverse('admin:get_default_templates', args=[org1.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_get_default_templates_404(self):
        self._login()
        response = self.client.get(
            reverse(
                'admin:get_default_templates', args=['d80a60a1415e4836b8f4bc588b084c29']
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_get_default_templates_404_inactive(self):
        (
            org1,
            org2,
            t1,
            t2,
            t3,
            inactive_org,
            inactive_t,
        ) = self._create_template_test_data()
        self._login()
        response = self.client.get(
            reverse('admin:get_default_templates', args=[inactive_org.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_get_default_templates_400(self):
        self._login()
        response = self.client.get(
            reverse('admin:get_default_templates', args=['wrong'])
        )
        self.assertEqual(response.status_code, 404)
