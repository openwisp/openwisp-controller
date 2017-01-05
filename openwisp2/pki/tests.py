from django.core.exceptions import ValidationError
from django.test import TestCase

from openwisp2.tests import TestOrganizationMixin

from .models import Ca, Cert


class TestPki(TestCase, TestOrganizationMixin):
    def _create_ca(self, **kwargs):
        options = dict(name='Test CA',
                       organization=None,
                       key_length='2048',
                       digest='sha256',
                       country_code='IT',
                       state='RM',
                       city='Rome',
                       email='test@test.com',
                       common_name='openwisp.org',
                       extensions=[])
        options.update(kwargs)
        ca = Ca(**options)
        ca.full_clean()
        ca.save()
        return ca

    def _create_cert(self, **kwargs):
        options = dict(name='TestCert',
                       organization=None,
                       ca=None,
                       key_length='2048',
                       digest='sha256',
                       country_code='IT',
                       state='RM',
                       city='Rome',
                       email='test@test.com',
                       common_name='openwisp.org',
                       extensions=[])
        options.update(kwargs)
        cert = Cert(**options)
        cert.full_clean()
        cert.save()
        return cert

    def test_ca_creation_with_org(self):
        org = self._create_org()
        ca = self._create_ca(organization=org)
        self.assertEqual(ca.organization_id, org.pk)

    def test_ca_creation_without_org(self):
        ca = self._create_ca()
        self.assertIsNone(ca.organization)

    def test_cert_and_ca_different_organization(self):
        org1 = self._create_org()
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
        org = self._create_org()
        ca = self._create_ca(organization=org)
        cert = self._create_cert(ca=ca, organization=org)
        self.assertEqual(ca.organization.pk, cert.organization.pk)
