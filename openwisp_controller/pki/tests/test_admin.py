from django.contrib import admin
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse
from swapper import load_model

from openwisp_controller.config.tests.utils import (
    CreateConfigMixin,
    CreateTemplateMixin,
)
from openwisp_users.tests.utils import TestOrganizationMixin

from ...tests.utils import TestAdminMixin
from .utils import TestPkiMixin

Ca = load_model("django_x509", "Ca")
Cert = load_model("django_x509", "Cert")
DeviceCertificate = load_model("config", "DeviceCertificate")
OrganizationUser = load_model("openwisp_users", "OrganizationUser")


class TestAdmin(
    TestPkiMixin,
    TestAdminMixin,
    CreateConfigMixin,
    CreateTemplateMixin,
    TestOrganizationMixin,
    TestCase,
):
    app_label = "pki"

    def _create_multitenancy_test_env(self, cert=False):
        org1 = self._create_org(name="test1org")
        org2 = self._create_org(name="test2org")
        inactive = self._create_org(name="inactive-org", is_active=False)
        operator = self._create_operator(organizations=[org1, inactive])
        administrator = self._create_administrator(organizations=[org1, inactive])
        ca1 = self._create_ca(name="Org1 CA", organization=org1)
        ca2 = self._create_ca(name="Org2 CA", organization=org2)
        ca_shared = self._create_ca(name="ca-shared", organization=None)
        ca_inactive = self._create_ca(name="ca-inactive", organization=inactive)
        data = dict(
            ca1=ca1,
            ca2=ca2,
            ca_inactive=ca_inactive,
            ca_shared=ca_shared,
            org1=org1,
            org2=org2,
            inactive=inactive,
            operator=operator,
            administrator=administrator,
        )
        if cert:
            cert1 = self._create_cert(name="Org1 Cert", ca=ca1, organization=org1)
            cert2 = self._create_cert(name="Org2 Cert", ca=ca2, organization=org2)
            cert_shared = self._create_cert(
                name="cert-shared", ca=ca_shared, organization=None
            )
            cert_inactive = self._create_cert(
                name="cert-inactive", ca=ca_inactive, organization=inactive
            )
            data.update(
                dict(
                    cert1=cert1,
                    cert_shared=cert_shared,
                    cert2=cert2,
                    cert_inactive=cert_inactive,
                )
            )
        return data

    def test_ca_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f"admin:{self.app_label}_ca_changelist"),
            visible=[data["ca1"].name, data["org1"].name],
            hidden=[
                data["ca2"].name,
                data["org2"].name,
                data["ca_inactive"].name,
                data["ca_shared"].name,
            ],
        )

    def test_ca_organization_fk_autocomplete_view(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=self._get_autocomplete_view_path(self.app_label, "ca", "organization"),
            visible=[data["org1"].name],
            hidden=[data["org2"].name, data["inactive"]],
            administrator=True,
        )

    def test_cert_queryset(self):
        data = self._create_multitenancy_test_env(cert=True)
        self._test_multitenant_admin(
            url=reverse(f"admin:{self.app_label}_cert_changelist"),
            visible=[data["cert1"].name, data["org1"].name],
            hidden=[
                data["cert2"].name,
                data["org2"].name,
                data["cert_inactive"].name,
                data["cert_shared"].name,
            ],
        )

    def test_cert_organization_fk_autocomplete_view(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=self._get_autocomplete_view_path(
                self.app_label, "cert", "organization"
            ),
            visible=[data["org1"].name],
            hidden=[data["org2"].name, data["inactive"]],
            administrator=True,
        )

    def test_cert_ca_fk_autocomplete_view(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=self._get_autocomplete_view_path(self.app_label, "cert", "ca"),
            visible=[data["ca1"].name],
            hidden=[data["ca2"].name, data["ca_inactive"].name],
            administrator=True,
        )

    def test_cert_changeform_200(self):
        org = self._create_org(name="test-org")
        self._create_operator(organizations=[org])
        self._login(username="operator", password="tester")
        ca = self._create_ca(name="ca", organization=org)
        cert = self._create_cert(name="cert", ca=ca, organization=org)
        url = reverse(f"admin:{self.app_label}_cert_change", args=[cert.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_change_bound_cert_organization_admin(self):
        org1 = self._create_org(name="org1", slug="org1")
        org2 = self._create_org(name="org2", slug="org2")
        ca = self._create_ca(name="ca")
        template = self._create_template(
            name="cert-template", type="cert", ca=ca, organization=org1, config={}
        )
        device = self._create_device(organization=org1, name="bound-cert-device")
        config = self._create_config(device=device)
        config.templates.add(template)
        cert = DeviceCertificate.objects.get(config=config, template=template).cert
        self._login()
        url = reverse(f"admin:{self.app_label}_cert_change", args=[cert.pk])
        params = {
            "name": cert.name,
            "organization": str(org2.pk),
            "ca": str(cert.ca.pk),
            "notes": cert.notes,
            "operation_type": "-",
        }
        response = self.client.post(url, params)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "errorlist")
        self.assertContains(response, "cannot be changed")
        cert.refresh_from_db()
        self.assertEqual(cert.organization_id, org1.pk)

    def test_ca_changelist_ignores_forged_shared_relation_params(self):
        data = self._create_multitenancy_test_env()
        self._login(username="administrator", password="tester")
        ca_admin = admin.site._registry[Ca]
        params = (
            "app_label=config&model_name=template&field_name=ca",
            "app_label=pki&model_name=cert&field_name=ca",
        )
        for param in params:
            with self.subTest(param):
                url = f'{reverse("admin:pki_ca_changelist")}?{param}'
                request = RequestFactory().get(url)
                request.resolver_match = resolve(url)
                request.user = data["administrator"]
                qs = ca_admin.get_queryset(request)
                self.assertIn(data["ca1"], qs)
                self.assertNotIn(data["ca_shared"], qs)

    def test_ca_change_view_ignores_forged_shared_relation_params(self):
        data = self._create_multitenancy_test_env()
        self._login(username="administrator", password="tester")
        params = (
            "app_label=config&model_name=template&field_name=ca",
            "app_label=pki&model_name=cert&field_name=ca",
        )
        for param in params:
            with self.subTest(param):
                url = (
                    f'{reverse("admin:pki_ca_change", args=[data["ca_shared"].pk])}'
                    f"?{param}"
                )
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, reverse("admin:index"))

    def test_ca_delete_view_ignores_forged_shared_relation_params(self):
        data = self._create_multitenancy_test_env()
        self._login(username="administrator", password="tester")
        params = (
            "app_label=config&model_name=template&field_name=ca",
            "app_label=pki&model_name=cert&field_name=ca",
        )
        for param in params:
            with self.subTest(param):
                url = (
                    f'{reverse("admin:pki_ca_delete", args=[data["ca_shared"].pk])}'
                    f"?{param}"
                )
                response = self.client.post(url, {"post": "yes"})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, reverse("admin:index"))
                self.assertTrue(Ca.objects.filter(pk=data["ca_shared"].pk).exists())

    def test_cert_changelist_ignores_forged_shared_relation_params(self):
        data = self._create_multitenancy_test_env(cert=True)
        self._login(username="administrator", password="tester")
        url = (
            f'{reverse("admin:pki_cert_changelist")}'
            "?app_label=config&model_name=template&field_name=blueprint_cert"
        )
        request = RequestFactory().get(url)
        request.resolver_match = resolve(url)
        request.user = data["administrator"]
        cert_admin = admin.site._registry[Cert]
        qs = cert_admin.get_queryset(request)
        self.assertIn(data["cert1"], qs)
        self.assertNotIn(data["cert_shared"], qs)

    def test_cert_change_view_ignores_forged_shared_relation_params(self):
        data = self._create_multitenancy_test_env(cert=True)
        self._login(username="administrator", password="tester")
        params = "?app_label=config&model_name=template&field_name=blueprint_cert"
        url = reverse("admin:pki_cert_change", args=[data["cert_shared"].pk]) + params
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin:index"))

    def test_cert_delete_view_ignores_forged_shared_relation_params(self):
        data = self._create_multitenancy_test_env(cert=True)
        self._login(username="administrator", password="tester")
        params = "?app_label=config&model_name=template&field_name=blueprint_cert"
        url = reverse("admin:pki_cert_delete", args=[data["cert_shared"].pk]) + params
        response = self.client.post(url, {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin:index"))
        self.assertTrue(Cert.objects.filter(pk=data["cert_shared"].pk).exists())

    def test_autocomplete_requires_source_admin_permission(self):
        data = self._create_multitenancy_test_env()
        user = self._create_user(
            username="ca-only",
            password="tester",
            email="ca-only@test.com",
            is_staff=True,
        )
        user.user_permissions.add(
            Permission.objects.get(codename="change_ca", content_type__app_label="pki")
        )
        OrganizationUser.objects.create(
            user=user,
            organization=data["org1"],
            is_admin=True,
        )
        user.organizations_dict
        self.client.force_login(user)
        url = (
            f'{reverse("admin:autocomplete")}'
            "?app_label=config&model_name=template&field_name=ca"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, data["ca1"].name)
        self.assertNotContains(response, data["ca_shared"].name)

    def test_changelist_recover_deleted_button(self):
        self._create_multitenancy_test_env()
        self._test_changelist_recover_deleted(self.app_label, "ca")
        self._test_changelist_recover_deleted(self.app_label, "cert")

    def test_recoverlist_operator_403(self):
        self._create_multitenancy_test_env()
        self._test_recoverlist_operator_403(self.app_label, "ca")
        self._test_recoverlist_operator_403(self.app_label, "cert")

    def test_admin_menu_groups(self):
        # Test menu group (openwisp-utils menu group) for Ca, Cert models
        self.client.force_login(self._get_admin())
        models = ["ca", "cert"]
        response = self.client.get(reverse("admin:index"))
        for model in models:
            with self.subTest(f"test menu group link for {model} model"):
                url = reverse(f"admin:{self.app_label}_{model}_changelist")
                self.assertContains(response, f' class="mg-link" href="{url}"')
        with self.subTest('test "Cas & Certificates" group is registered'):
            self.assertContains(
                response,
                '<div class="mg-dropdown-label">Cas & Certificates </div>',
                html=True,
            )
