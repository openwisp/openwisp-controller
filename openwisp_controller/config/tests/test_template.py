from django.core.exceptions import ValidationError
from django.test import TestCase

from openwisp_users.tests.utils import TestOrganizationMixin

from . import CreateConfigTemplateMixin, TestVpnX509Mixin
from ...pki.models import Ca, Cert
from ..models import Config, Template, Vpn


class TestTemplate(CreateConfigTemplateMixin, TestVpnX509Mixin,
                   TestOrganizationMixin, TestCase):
    ca_model = Ca
    cert_model = Cert
    config_model = Config
    template_model = Template
    vpn_model = Vpn

    def test_template_with_org(self):
        org = self._create_org()
        template = self._create_template(organization=org)
        self.assertEqual(template.organization_id, org.pk)

    def test_template_without_org(self):
        template = self._create_template()
        self.assertIsNone(template.organization)

    def test_template_with_shared_vpn(self):
        vpn = self._create_vpn()  # shared VPN
        org = self._create_org()
        template = self._create_template(organization=org, type='vpn', vpn=vpn)
        self.assertIsNone(vpn.organization)
        self.assertEqual(template.vpn_id, vpn.pk)

    def test_template_and_vpn_different_organization(self):
        org1 = self._create_org()
        vpn = self._create_vpn(organization=org1)
        org2 = self._create_org(name='test org2', slug='test-org2')
        try:
            self._create_template(organization=org2, type='vpn', vpn=vpn)
        except ValidationError as e:
            self.assertIn('organization', e.message_dict)
            self.assertIn('related VPN server match', e.message_dict['organization'][0])
        else:
            self.fail('ValidationError not raised')

    def test_org_default_template(self):
        org1 = self._create_org(name='org1')
        org2 = self._create_org(name='org2')
        self._create_template(organization=org1, name='t1', default=True)
        self._create_template(organization=org2, name='t2', default=True)
        c1 = self._create_config(organization=org1, name='c1')
        self.assertEqual(c1.templates.count(), 1)
        self.assertEqual(c1.templates.filter(name='t1').count(), 1)
        c2 = self._create_config(organization=org2,
                                 name='c2',
                                 mac_address='00:00:00:11:22:33',
                                 key='1234567890')
        self.assertEqual(c2.templates.count(), 1)
        self.assertEqual(c2.templates.filter(name='t2').count(), 1)

    def test_org_default_shared_template(self):
        org1 = self._create_org(name='org1')
        self._create_template(organization=org1, name='t1', default=True)
        self._create_template(organization=None, name='t2', default=True)
        c1 = self._create_config(organization=org1, name='c1')
        self.assertEqual(c1.templates.count(), 2)
        self.assertEqual(c1.templates.filter(name='t1').count(), 1)
        self.assertEqual(c1.templates.filter(name='t2').count(), 1)
