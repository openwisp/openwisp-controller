from unittest import mock

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from django.core.exceptions import ValidationError
from django.db.models.query import QuerySet
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

    def test_renew_revoked_cert(self):
        cert = self._create_cert(name="cert1")
        old_serial_num = cert.serial_number

        cert.revoke()

        with self.assertRaises(ValidationError):
            cert.renew()

        cert.refresh_from_db()
        self.assertEqual(int(cert.serial_number), int(old_serial_num))
        self.assertTrue(cert.revoked)

    def test_renew_uses_select_for_update(self):
        cert = self._create_cert(name="cert1")

        select_for_update = QuerySet.select_for_update
        with mock.patch.object(
            QuerySet,
            "select_for_update",
            autospec=True,
            side_effect=select_for_update,
        ) as mocked_select_for_update:
            cert.renew()

        mocked_select_for_update.assert_called_once_with(mock.ANY)
        self.assertEqual(mocked_select_for_update.call_args.args[0].model, Cert)

    def test_revoke_uses_select_for_update(self):
        cert = self._create_cert(name="cert1")

        select_for_update = QuerySet.select_for_update
        with mock.patch.object(
            QuerySet,
            "select_for_update",
            autospec=True,
            side_effect=select_for_update,
        ) as mocked_select_for_update:
            cert.revoke()

        mocked_select_for_update.assert_called_once_with(mock.ANY)
        self.assertEqual(mocked_select_for_update.call_args.args[0].model, Cert)

    def test_unique_together_org_none(self):
        ca = self._create_ca(organization=None, common_name="common_name")
        with self.assertRaises(ValidationError):
            self._create_ca(organization=None, common_name="common_name")
        self._create_cert(ca=ca)
        with self.assertRaises(ValidationError):
            self._create_cert(ca=ca)
