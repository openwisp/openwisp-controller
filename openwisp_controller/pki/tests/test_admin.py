from django.test import TestCase
from django.urls import reverse
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin

from ...tests.utils import TestAdminMixin
from .utils import TestPkiMixin

Ca = load_model('django_x509', 'Ca')
Cert = load_model('django_x509', 'Cert')


class TestAdmin(TestPkiMixin, TestAdminMixin, TestOrganizationMixin, TestCase):
    app_label = 'pki'

    def _create_multitenancy_test_env(self, cert=False):
        org1 = self._create_org(name='test1org')
        org2 = self._create_org(name='test2org')
        inactive = self._create_org(name='inactive-org', is_active=False)
        operator = self._create_operator(organizations=[org1, inactive])
        administrator = self._create_administrator(organizations=[org1, inactive])
        ca1 = self._create_ca(name='ca1', organization=org1)
        ca2 = self._create_ca(name='ca2', organization=org2)
        ca_shared = self._create_ca(name='ca-shared', organization=None)
        ca_inactive = self._create_ca(name='ca-inactive', organization=inactive)
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
            cert1 = self._create_cert(name='cert1', ca=ca1, organization=org1)
            cert2 = self._create_cert(name='cert2', ca=ca2, organization=org2)
            cert_shared = self._create_cert(
                name='cert-shared', ca=ca_shared, organization=None
            )
            cert_inactive = self._create_cert(
                name='cert-inactive', ca=ca_inactive, organization=inactive
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
            url=reverse(f'admin:{self.app_label}_ca_changelist'),
            visible=[data['ca1'].name, data['org1'].name],
            hidden=[
                data['ca2'].name,
                data['org2'].name,
                data['ca_inactive'].name,
                data['ca_shared'].name,
            ],
        )

    def test_ca_organization_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_ca_add'),
            visible=[data['org1'].name],
            hidden=[data['org2'].name, data['inactive']],
            select_widget=True,
            administrator=True,
        )

    def test_cert_queryset(self):
        data = self._create_multitenancy_test_env(cert=True)
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_cert_changelist'),
            visible=[data['cert1'].name, data['org1'].name],
            hidden=[
                data['cert2'].name,
                data['org2'].name,
                data['cert_inactive'].name,
                data['cert_shared'].name,
            ],
        )

    def test_cert_organization_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_cert_add'),
            visible=[data['org1'].name],
            hidden=[data['org2'].name, data['inactive']],
            select_widget=True,
            administrator=True,
        )

    def test_cert_ca_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_cert_add'),
            visible=[data['ca1'].name, data['ca_shared'].name],
            hidden=[data['ca2'].name, data['ca_inactive'].name],
            select_widget=True,
            administrator=True,
        )

    def test_cert_changeform_200(self):
        org = self._create_org(name='test-org')
        self._create_operator(organizations=[org])
        self._login(username='operator', password='tester')
        ca = self._create_ca(name='ca', organization=org)
        cert = self._create_cert(name='cert', ca=ca, organization=org)
        url = reverse(f'admin:{self.app_label}_cert_change', args=[cert.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_changelist_recover_deleted_button(self):
        self._create_multitenancy_test_env()
        self._test_changelist_recover_deleted(self.app_label, 'ca')
        self._test_changelist_recover_deleted(self.app_label, 'cert')

    def test_recoverlist_operator_403(self):
        self._create_multitenancy_test_env()
        self._test_recoverlist_operator_403(self.app_label, 'ca')
        self._test_recoverlist_operator_403(self.app_label, 'cert')

    def test_admin_menu_groups(self):
        # Test menu group (openwisp-utils menu group) for Ca, Cert models
        self.client.force_login(self._get_admin())
        models = ['ca', 'cert']
        response = self.client.get(reverse('admin:index'))
        for model in models:
            with self.subTest(f'test menu group link for {model} model'):
                url = reverse(f'admin:{self.app_label}_{model}_changelist')
                self.assertContains(response, f' class="mg-link" href="{url}"')
        with self.subTest('test "Cas & Certificates" group is registered'):
            self.assertContains(
                response,
                '<div class="mg-dropdown-label">Cas & Certificates </div>',
                html=True,
            )
