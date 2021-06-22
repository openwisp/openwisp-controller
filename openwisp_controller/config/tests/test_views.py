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

    def test_get_relevant_templates_without_backend_filter(self):
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
        with self.assertNumQueries(4):
            response = self.client.get(
                reverse('admin:get_relevant_templates', args=[org1.pk])
            )
        template = response.json()
        self.assertEqual(template, {})

    def test_get_relevant_templates_with_backend_filtering(self):
        org1 = self._create_org(name='org1')
        t1 = self._create_template(
            name='t1',
            organization=org1,
            default=True,
            backend='netjsonconfig.OpenWrt',
            required=True,
        )
        t2 = self._create_template(
            name='t2',
            organization=org1,
            default=True,
            backend='netjsonconfig.OpenWisp',
            required=True,
        )
        self._login()

        with self.assertNumQueries(4):
            response = self.client.get(
                reverse('admin:get_relevant_templates', args=[org1.pk]),
                {'backend': 'netjsonconfig.OpenWrt'},
            )
        templates = response.json()
        self.assertEqual(len(templates), 1)
        self.assertEqual(
            templates,
            {
                str(t1.pk): {
                    'required': t1.required,
                    'default': t1.default,
                    'name': t1.name,
                }
            },
        )
        self.assertNotIn(str(t2.pk), templates)

        response = self.client.get(
            reverse('admin:get_relevant_templates', args=[org1.pk]),
            {'backend': 'netjsonconfig.OpenWisp'},
        )
        templates = response.json()
        self.assertEqual(len(templates), 1)
        self.assertEqual(
            templates,
            {
                str(t2.pk): {
                    'required': t2.required,
                    'default': t2.default,
                    'name': t2.name,
                }
            },
        )
        self.assertNotIn(str(t1.pk), templates)

    def test_get_relevant_templates_authorization(self):
        org1 = self._create_org(name='org1')
        with self.subTest('Unauthenticated user'):
            # Unauthenticated users will be redirected to login page
            response = self.client.get(
                reverse('admin:get_relevant_templates', args=[org1.pk])
            )
            self.assertEqual(response.status_code, 302)

        with self.subTest('Authenticated non-staff user'):
            # Non-staff users will be redirected to login page of admin
            # and will be asked to login with a staff account
            user = self._create_user()
            self.client.force_login(user)
            response = self.client.get(
                reverse('admin:get_relevant_templates', args=[org1.pk])
            )
            self.assertEqual(response.status_code, 302)
            response = self.client.get(
                reverse('admin:get_relevant_templates', args=[org1.pk]), follow=True
            )
            self.assertContains(response, 'not authorized')

        with self.subTest('User requests data of other organization'):
            org_owner = self._create_org_owner()
            user = org_owner.organization_user.user
            user.is_staff = True
            user.save()
            self.client.force_login(user)
            response = self.client.get(
                reverse('admin:get_relevant_templates', args=[org1.pk])
            )
            self.assertEqual(response.status_code, 403)

        with self.subTest('Superuser requests data for any organization'):
            self._login()
            response = self.client.get(
                reverse('admin:get_relevant_templates', args=[org1.pk])
            )
            self.assertEqual(response.status_code, 200)

    def test_get_relevant_templates_404(self):
        self._login()
        response = self.client.get(
            reverse(
                'admin:get_relevant_templates',
                args=['d80a60a1415e4836b8f4bc588b084c29'],
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_get_relevant_templates_404_inactive(self):
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
            reverse('admin:get_relevant_templates', args=[inactive_org.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_get_relevant_templates_400(self):
        self._login()
        response = self.client.get(
            reverse('admin:get_relevant_templates', args=['wrong'])
        )
        self.assertEqual(response.status_code, 404)

    def get_template_default_values_authorization(self):
        org1 = self._get_org()
        org1_template = self._create_template(
            organization=org1, default_values={'org1': 'secret1'}
        )
        org2 = self._create_org(name='org2')
        org2_template = self._create_template(
            organization=org2, default_values={'org2': 'secret2'}
        )
        shared_template = self._create_template(
            name='shared-template', default_values={'key': 'value'}
        )
        url = (
            reverse('admin:get_template_default_values')
            + f'?pks={org1_template.pk},{org2_template.pk},{shared_template.pk}'
        )

        with self.subTest('Unauthenticated user'):
            # Unauthenticated users will be redirected to login page
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)

        with self.subTest('Authenticated non-staff user'):
            # Non-staff users will be redirected to login page of admin
            # and will be asked to login with a staff account
            user = self._create_user()
            self.client.force_login(user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            response = self.client.get(
                reverse('admin:get_relevant_templates', args=[org1.pk]), follow=True
            )
            self.assertContains(response, 'not authorized')

        with self.subTest('Org admin requests data of other organization'):
            org1_admin = self._create_org_user(organization=org1, is_admin=True)
            org1_user = org1_admin.user
            org1_user.is_staff = True
            org1_user.save()
            self.client.force_login(org1_user)
            expected_response = {'default_values': {'org1': 'secret1', 'key': 'value'}}
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(response.content, expected_response)

        with self.subTest('Superuser requests data for any organization'):
            self._login()
            response = self.client.get(url)
            expected_response = {
                'default_values': {'org1': 'secret1', 'org2': 'secret2', 'key': 'value'}
            }
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(response.content, expected_response)

    def get_template_default_values_same_keys(self):
        self._login()
        # Atleast 4 templates are required to create enough entropy in database
        # to make the test fail consistently without patch
        template1 = self._create_template(name='VNI 1', default_values={'vn1': '1'})
        template2 = self._create_template(
            name='VNI 2', default_values={'vn1': '2', 'vn2': '20'}
        )
        template3 = self._create_template(
            name='VNI 3', default_values={'vn1': '3', 'vn2': '30', 'vn3': '300'}
        )
        template4 = self._create_template(
            name='VNI 4', default_values={'vn1': '4', 'vn2': '40', 'vn3': '400'}
        )
        template5 = self._create_template(
            name='VNI 5', default_values={'vn1': '5', 'vn2': '50', 'vn3': '500'}
        )
        url = reverse('admin:get_template_default_values')
        templates = [template5, template4, template3, template2, template1]
        template_pks = ','.join([str(template.pk) for template in templates])
        response = self.client.get(url, {'pks': template_pks})
        default_values = response.json()['default_values']
        self.assertEqual(default_values['vn1'], '1')
        self.assertEqual(default_values['vn2'], '20')
        self.assertEqual(default_values['vn3'], '300')
