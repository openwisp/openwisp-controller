import json

from django.contrib.auth.models import Permission
from django.db.models import Q
from django.test import TestCase
from django.urls import reverse

from openwisp2.users.models import OrganizationUser, User

from . import CreateAdminMixin, CreateConfigTemplateMixin, TestVpnX509Mixin
from ...pki.models import Ca, Cert
from ...tests import TestOrganizationMixin
from ..models import Config, Template, Vpn


class TestAdmin(CreateConfigTemplateMixin, CreateAdminMixin,
                TestVpnX509Mixin, TestOrganizationMixin, TestCase):
    """
    tests for Config model
    """
    ca_model = Ca
    cert_model = Cert
    config_model = Config
    template_model = Template
    vpn_model = Vpn
    operator_permissions = Permission.objects.filter(Q(codename__endswith='config') |
                                                     Q(codename__endswith='template'))

    def setUp(self):
        super(TestAdmin, self).setUp()
        self._login()

    def _create_operator(self, permissions=operator_permissions, organizations=[]):
        operator = User.objects.create_user(username='operator',
                                            password='tester',
                                            email='operator@test.com',
                                            is_staff=True)
        for perm in permissions:
            operator.user_permissions.add(perm)
        for organization in organizations:
            OrganizationUser.objects.create(user=operator, organization=organization)
        return operator

    def test_config_and_template_different_organization(self):
        org1 = self._create_org()
        template = self._create_template(organization=org1)
        org2 = self._create_org(name='test org2', slug='test-org2')
        config = self._create_config(organization=org2)
        path = reverse('admin:config_config_change', args=[config.pk])
        # ensure it fails with error
        response = self.client.post(path, {'templates': str(template.pk), 'key': self.TEST_KEY})
        self.assertIn('errors field-templates', str(response.content))
        # remove conflicting template and ensure doesn't error
        response = self.client.post(path, {'templates': '', 'key': self.TEST_KEY})
        self.assertNotIn('errors field-templates', str(response.content))

    def test_preview_config(self):
        org = self._create_org()
        self._create_template(organization=org)
        templates = Template.objects.all()
        path = reverse('admin:config_config_preview')
        config = json.dumps({
            'interfaces': [
                {
                    'name': 'eth0',
                    'type': 'ethernet',
                    'addresses': [
                        {
                            'family': 'ipv4',
                            'proto': 'dhcp'
                        }
                    ]
                }
            ]
        })
        data = {
            'name': 'test-config',
            'organization': org.pk,
            'mac_address': self.TEST_MAC_ADDRESS,
            'backend': 'netjsonconfig.OpenWrt',
            'config': config,
            'csrfmiddlewaretoken': 'test',
            'templates': ','.join([str(t.pk) for t in templates])
        }
        response = self.client.post(path, data)
        self.assertContains(response, '<pre class="djnjc-preformatted')
        self.assertContains(response, 'eth0')
        self.assertContains(response, 'dhcp')

    def _create_multitenancy_test_env(self):
        self.client.logout()
        org1 = self._create_org(name='test1org')
        org2 = self._create_org(name='test2org')
        self._create_operator(organizations=[org1])
        self.client.login(username='operator', password='tester')
        t1 = self._create_template(name='template1org', organization=org1)
        t2 = self._create_template(name='template2org', organization=org2)
        c1 = self._create_config(name='org1-config', organization=org1)
        c2 = self._create_config(name='org2-config',
                                      organization=org2,
                                      key=None,
                                      mac_address='00:11:22:33:44:56')
        c1.templates.add(t1)
        c2.templates.add(t2)
        return c1, c2, t1, t2

    def test_config_queryset(self):
        c1, c2, t1, t2 = self._create_multitenancy_test_env()
        path = reverse('admin:config_config_changelist')
        response = self.client.get(path)
        self.assertContains(response, c1.name)
        self.assertNotContains(response, c2.name)

    def test_config_organization_fk_queryset(self):
        c1, c2, t1, t2 = self._create_multitenancy_test_env()
        path = reverse('admin:config_config_add')
        response = self.client.get(path)
        self.assertContains(response, '{0}</option>'.format(c1.organization.name))
        self.assertNotContains(response, '{0}</option>'.format(c2.organization.name))

    def test_config_templates_m2m_queryset(self):
        c1, c2, t1, t2 = self._create_multitenancy_test_env()
        t3 = self._create_template(name='t3-shared', organization=None)
        path = reverse('admin:config_config_add')
        response = self.client.get(path)
        self.assertContains(response, str(t1))
        self.assertNotContains(response, str(t2))
        # contains shared template
        self.assertContains(response, str(t3))

    def test_template_queryset(self):
        c1, c2, t1, t2 = self._create_multitenancy_test_env()
        path = reverse('admin:config_template_changelist')
        response = self.client.get(path)
        self.assertContains(response, t1.name)
        self.assertNotContains(response, t2.name)

    def test_template_organization_fk_queryset(self):
        c1, c2, t1, t2 = self._create_multitenancy_test_env()
        path = reverse('admin:config_template_add')
        response = self.client.get(path)
        self.assertContains(response, '{0}</option>'.format(t1.organization.name))
        self.assertNotContains(response, '{0}</option>'.format(t2.organization.name))

    def test_template_vpn_fk_queryset(self):
        c1, c2, t1, t2 = self._create_multitenancy_test_env()
        vpn1 = self._create_vpn(name='vpn1org', organization=t1.organization)
        vpn2 = self._create_vpn(name='vpn2org', organization=t2.organization)
        vpn3 = self._create_vpn(name='vpn3shared', organization=None)
        t1.type = 'vpn-client'
        t1.vpn = vpn1
        t1.save()
        path = reverse('admin:config_template_add')
        response = self.client.get(path)
        self.assertContains(response, '{0}</option>'.format(vpn1.name))
        self.assertNotContains(response, '{0}</option>'.format(vpn2.name))
        # containes shared VPN
        self.assertContains(response, '{0}</option>'.format(vpn3.name))
