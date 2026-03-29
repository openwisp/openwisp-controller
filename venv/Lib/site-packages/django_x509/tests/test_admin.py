from copy import deepcopy

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openwisp_utils.tests import AdminActionPermTestMixin
from swapper import load_model

from . import MessagingRequest

User = get_user_model()
Ca = load_model("django_x509", "Ca")
Cert = load_model("django_x509", "Cert")


class MockSuperUser:
    def has_perm(self, perm):
        return True


request = MessagingRequest()
request.user = MockSuperUser()

ca_fields = [
    "operation_type",
    "name",
    "notes",
    "key_length",
    "digest",
    "validity_start",
    "validity_end",
    "country_code",
    "state",
    "city",
    "organization_name",
    "organizational_unit_name",
    "email",
    "common_name",
    "extensions",
    "serial_number",
    "certificate",
    "private_key",
    "passphrase",
]

cert_fields = [
    "operation_type",
    "name",
    "ca",
    "notes",
    "key_length",
    "digest",
    "validity_start",
    "validity_end",
    "country_code",
    "state",
    "city",
    "organization_name",
    "organizational_unit_name",
    "email",
    "common_name",
    "extensions",
    "serial_number",
    "certificate",
    "private_key",
    "passphrase",
]

ca_readonly = [
    "key_length",
    "digest",
    "validity_start",
    "validity_end",
    "country_code",
    "state",
    "city",
    "organization_name",
    "organizational_unit_name",
    "email",
    "common_name",
    "serial_number",
    "certificate",
    "private_key",
    "created",
    "modified",
]

cert_readonly = [
    "revoked",
    "revoked_at",
    "created",
    "modified",
    "created",
    "modified",
    "created",
    "modified",
    "created",
    "modified",
    "created",
    "modified",
    "created",
    "modified",
]


class ModelAdminTests(AdminActionPermTestMixin, TestCase):
    app_label = "django_x509"
    ca_admin = admin.site._registry[Ca].__class__
    cert_admin = admin.site._registry[Cert].__class__

    def setUp(self):
        self.ca = Ca.objects.create()
        self.cert = Cert.objects.create(ca_id=self.ca.pk)
        self.cert.ca = self.ca
        self.site = AdminSite()

    def test_modeladmin_str_ca(self):
        ma = self.ca_admin(Ca, self.site)
        self.assertEqual(str(ma), f"{self.app_label}.CaAdmin")

    def test_modeladmin_str_certr(self):
        ma = self.cert_admin(Cert, self.site)
        self.assertEqual(str(ma), f"{self.app_label}.CertAdmin")

    def test_default_fields_ca(self):
        ma = self.ca_admin(Ca, self.site)
        self.assertEqual(list(ma.get_form(request).base_fields), ca_fields)
        ca_fields.insert(len(ca_fields), "created")
        ca_fields.insert(len(ca_fields), "modified")
        self.assertEqual(list(ma.get_fields(request)), ca_fields)
        index = ca_fields.index("extensions")
        pass_index = ca_fields.index("passphrase")
        ca_fields.remove("extensions")
        ca_fields.remove("passphrase")
        self.assertEqual(list(ma.get_fields(request, self.ca)), ca_fields)
        ca_fields.insert(index, "extensions")
        ca_fields.insert(pass_index, "passphrase")

    def test_default_fields_cert(self):
        ma = self.cert_admin(Cert, self.site)
        self.assertEqual(list(ma.get_form(request).base_fields), cert_fields)
        cert_fields.insert(4, "revoked")
        cert_fields.insert(5, "revoked_at")
        cert_fields.insert(len(cert_fields), "created")
        cert_fields.insert(len(cert_fields), "modified")
        self.assertEqual(list(ma.get_fields(request)), cert_fields)
        index = cert_fields.index("extensions")
        pass_index = cert_fields.index("passphrase")
        cert_fields.remove("extensions")
        cert_fields.remove("passphrase")
        self.assertEqual(list(ma.get_fields(request, self.cert)), cert_fields)
        cert_fields.insert(index, "extensions")
        cert_fields.insert(pass_index, "passphrase")

    def test_default_fieldsets_ca(self):
        ma = self.ca_admin(Ca, self.site)
        self.assertEqual(ma.get_fieldsets(request), [(None, {"fields": ca_fields})])

    def test_default_fieldsets_cert(self):
        ma = self.cert_admin(Cert, self.site)
        self.assertEqual(ma.get_fieldsets(request), [(None, {"fields": cert_fields})])

    def test_readonly_fields_Ca(self):
        ma = self.ca_admin(Ca, self.site)
        self.assertEqual(ma.get_readonly_fields(request), ("created", "modified"))
        self.assertEqual(ma.get_readonly_fields(request, self.ca), tuple(ca_readonly))
        ca_readonly.remove("created")
        ca_readonly.remove("modified")

    def test_readonly_fields_Cert(self):
        ma = self.cert_admin(Cert, self.site)
        self.assertEqual(ma.get_readonly_fields(request), cert_readonly)
        ca_readonly.append("ca")
        self.assertEqual(
            ma.get_readonly_fields(request, self.cert),
            tuple(ca_readonly + cert_readonly),
        )

    def test_ca_url(self):
        ma = self.cert_admin(Cert, self.site)
        self.assertEqual(
            ma.ca_url(self.cert), f'<a href="/admin/{self.app_label}/ca/1/change/"></a>'
        )

    def test_revoke_action(self):
        ma = self.cert_admin(Cert, self.site)
        ma.revoke_action(request, [self.cert])
        m = list(request.get_messages())
        self.assertEqual(len(m), 1)
        self.assertEqual(str(m[0]), "1 certificate was revoked.")

    def test_revoke_action_perms(self):
        user = User.objects.create(
            username="tester", email="tester@openwisp.org", is_staff=True
        )
        cert = Cert.objects.create(
            name="test_cert", ca=Ca.objects.create(name="test_ca")
        )
        self._test_action_permission(
            path=reverse(f"admin:{self.app_label}_cert_changelist"),
            action="revoke_action",
            user=user,
            obj=cert,
            message="1 certificate was revoked.",
            required_perms=["change"],
        )

    def test_renew_ca_action(self):
        req = deepcopy(request)
        ca = Ca.objects.create(name="test_ca")
        cert = Cert.objects.create(name="test_cert", ca=ca)
        old_ca_cert = ca.certificate
        old_ca_key = ca.private_key
        old_ca_end = ca.validity_end
        old_ca_serial_number = ca.serial_number
        old_cert_cert = cert.certificate
        old_cert_key = cert.private_key
        old_cert_end = cert.validity_end
        old_cert_serial_number = cert.serial_number
        ma = self.ca_admin(Ca, self.site)
        req.POST.update({"post": None})
        r = ma.renew_ca(req, [ca])
        self.assertEqual(r.status_code, 200)
        req.POST.update({"post": "yes"})
        ma.renew_ca(req, [ca])
        message = req.get_message_strings()
        cert.refresh_from_db()
        self.assertNotEqual(old_ca_cert, ca.certificate)
        self.assertNotEqual(old_ca_key, ca.private_key)
        self.assertLess(old_ca_end, ca.validity_end)
        self.assertNotEqual(old_ca_serial_number, ca.serial_number)
        self.assertNotEqual(old_cert_serial_number, cert.serial_number)
        self.assertLess(old_cert_end, cert.validity_end)
        self.assertNotEqual(old_cert_key, cert.private_key)
        self.assertNotEqual(old_cert_cert, cert.certificate)
        self.assertEqual(len(message), 1)
        self.assertEqual(
            message[0],
            "1 CA and its related certificates have been successfully renewed",
        )

    def test_renew_ca_action_perms(self):
        """
        This test verifies that only users with change permission
        can perform the renew operation for CAs and certificates.
        """
        user = User.objects.create(
            username="tester", email="tester@openwisp.org", is_staff=True
        )
        ca = Ca.objects.create(name="test_ca")
        self._test_action_permission(
            path=reverse(f"admin:{self.app_label}_ca_changelist"),
            action="renew_ca",
            user=user,
            obj=ca,
            message="1 CA and its related certificates have been successfully renewed",
            required_perms=["change"],
        )

    def test_renew_cert_action(self):
        req = deepcopy(request)
        ca = Ca.objects.create(name="test_ca")
        cert = Cert.objects.create(name="test_cert", ca=ca)
        old_ca_cert = ca.certificate
        old_ca_key = ca.private_key
        old_ca_end = ca.validity_end
        old_ca_serial_number = ca.serial_number
        old_cert_cert = cert.certificate
        old_cert_key = cert.private_key
        old_cert_end = cert.validity_end
        old_cert_serial_number = cert.serial_number
        ma = self.cert_admin(Cert, self.site)
        req.POST.update({"post": None})
        r = ma.renew_cert(req, [cert])
        self.assertEqual(r.status_code, 200)
        req.POST.update({"post": "yes"})
        ma.renew_cert(req, [cert])
        message = req.get_message_strings()
        self.assertNotEqual(old_cert_serial_number, cert.serial_number)
        self.assertLess(old_cert_end, cert.validity_end)
        self.assertNotEqual(old_cert_key, cert.private_key)
        self.assertNotEqual(old_cert_cert, cert.certificate)
        self.assertEqual(old_ca_cert, ca.certificate)
        self.assertEqual(old_ca_key, ca.private_key)
        self.assertEqual(old_ca_end, ca.validity_end)
        self.assertEqual(old_ca_serial_number, ca.serial_number)
        self.assertEqual(len(message), 1)
        self.assertEqual(message[0], "1 Certificate has been successfully renewed")

    def test_renew_cert_action_perms(self):
        user = User.objects.create(
            username="tester", email="tester@openwisp.org", is_staff=True
        )
        cert = Cert.objects.create(
            name="test_cert", ca=Ca.objects.create(name="test_ca")
        )
        self._test_action_permission(
            path=reverse(f"admin:{self.app_label}_cert_changelist"),
            action="renew_cert",
            user=user,
            obj=cert,
            message="1 Certificate has been successfully renewed",
            required_perms=["change"],
        )
