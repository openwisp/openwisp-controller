from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from OpenSSL import crypto
from swapper import load_model

from openwisp_controller.tests.utils import TestAdminMixin
from openwisp_users.tests.utils import TestOrganizationMixin

from .utils import TestPkiMixin

Ca = load_model('django_x509', 'Ca')
Cert = load_model('django_x509', 'Cert')


class TestModels(TestAdminMixin, TestPkiMixin, TestOrganizationMixin, TestCase):
    def test_ca_creation_with_org(self):
        org = self._get_org()
        ca = self._create_ca(organization=org)
        self.assertEqual(ca.organization_id, org.pk)

    def test_ca_creation_without_org(self):
        ca = self._create_ca()
        self.assertIsNone(ca.organization)

    def test_cert_and_ca_different_organization(self):
        org1 = self._get_org()
        ca = self._create_ca(organization=org1)
        org2 = self._create_org(name='test org2', slug='test-org2')
        try:
            self._create_cert(ca=ca, organization=org2)
        except ValidationError as e:
            self.assertIn('organization', e.message_dict)
            self.assertIn('related CA match', e.message_dict['organization'][0])
        else:
            self.fail('ValidationError not raised')

    def test_cert_creation(self):
        org = self._get_org()
        ca = self._create_ca(organization=org)
        cert = self._create_cert(ca=ca, organization=org)
        self.assertEqual(ca.organization.pk, cert.organization.pk)

    def test_cert_validate_org_relation_no_rel(self):
        cert = Cert()
        with self.assertRaises(ValidationError):
            cert.full_clean()

    def test_crl_view(self):
        self._login()
        ca = self._create_ca()
        response = self.client.get(reverse('admin:crl', args=[ca.pk]))
        self.assertEqual(response.status_code, 200)
        crl = crypto.load_crl(crypto.FILETYPE_PEM, response.content)
        revoked_list = crl.get_revoked()
        self.assertIsNone(revoked_list)

    def test_unique_together_org_none(self):
        ca = self._create_ca(organization=None, common_name='common_name')
        with self.assertRaises(ValidationError):
            self._create_ca(organization=None, common_name='common_name')
        self._create_cert(ca=ca)
        with self.assertRaises(ValidationError):
            self._create_cert(ca=ca)
