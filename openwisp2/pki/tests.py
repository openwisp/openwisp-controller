from django.test import TestCase

from openwisp2.tests import TestOrganizationMixin

from .models import Ca


class TestPki(TestCase, TestOrganizationMixin):
    def test_ca_creation_with_org(self):
        org = self._create_org()
        ca = self._create_ca(organization=org)
        self.assertEqual(ca.organization_id, org.pk)

    def test_ca_creation_without_org(self):
        ca = self._create_ca()
        self.assertIsNone(ca.organization)

    def _create_ca(self, **kwargs):
        options = dict(name='newcert',
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
