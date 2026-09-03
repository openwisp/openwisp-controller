from cryptography import x509
from cryptography.hazmat.backends import default_backend
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from swapper import load_model

from openwisp_controller.tests.utils import TestAdminMixin
from openwisp_users.tests.utils import TestOrganizationMixin

from .utils import TestPkiMixin

Ca = load_model("django_x509", "Ca")
Cert = load_model("django_x509", "Cert")


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
        org2 = self._create_org(name="test org2", slug="test-org2")
        try:
            self._create_cert(ca=ca, organization=org2)
        except ValidationError as e:
            self.assertIn("organization", e.message_dict)
            self.assertIn("related CA match", e.message_dict["organization"][0])
        else:
            self.fail("ValidationError not raised")

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
        response = self.client.get(reverse("admin:crl", args=[ca.pk]))
        self.assertEqual(response.status_code, 200)
        crl = x509.load_pem_x509_crl(response.content, default_backend())
        revoked_list = [cert for cert in crl]
        self.assertEqual(revoked_list, [])

    def test_unique_together_org_none(self):
        ca = self._create_ca(organization=None, common_name="common_name")
        with self.assertRaises(ValidationError):
            self._create_ca(organization=None, common_name="common_name")
        self._create_cert(ca=ca)
        with self.assertRaises(ValidationError):
            self._create_cert(ca=ca)

    def test_renew_revoked_cert_raises_validation_error(self):
        cert = self._create_cert()
        old_serial = cert.serial_number
        cert.revoke()
        crl_bytes_before = (
            cert.ca.crl
            if isinstance(cert.ca.crl, bytes)
            else cert.ca.crl.encode("utf-8")
        )
        crl_before = x509.load_pem_x509_crl(crl_bytes_before, default_backend())
        revoked_serials_before = [r.serial_number for r in crl_before]
        self.assertIn(old_serial, revoked_serials_before)
        with self.assertRaises(ValidationError):
            cert.renew()
        cert.refresh_from_db()
        self.assertEqual(cert.serial_number, old_serial)
        self.assertTrue(cert.revoked)
        crl_bytes_after = (
            cert.ca.crl
            if isinstance(cert.ca.crl, bytes)
            else cert.ca.crl.encode("utf-8")
        )
        crl_after = x509.load_pem_x509_crl(crl_bytes_after, default_backend())
        revoked_serials_after = [r.serial_number for r in crl_after]
        self.assertIn(old_serial, revoked_serials_after)
        self.assertEqual(revoked_serials_after, revoked_serials_before)
