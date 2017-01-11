from django.core.exceptions import ValidationError
from django.test import TestCase
from django_netjsonconfig.tests import CreateTemplateMixin

from . import TestVpnX509Mixin
from ...pki.models import Ca, Cert
from ...tests import TestOrganizationMixin
from ..models import Template, Vpn


class TestTemplate(CreateTemplateMixin, TestVpnX509Mixin,
                   TestOrganizationMixin, TestCase):
    ca_model = Ca
    cert_model = Cert
    vpn_model = Vpn
    template_model = Template

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
