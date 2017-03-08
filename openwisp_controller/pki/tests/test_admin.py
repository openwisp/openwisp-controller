from django.test import TestCase
from django.urls import reverse

from openwisp_users.tests.utils import TestOrganizationMixin

from . import TestPkiMixin
from ...tests.utils import TestAdminMixin
from ..models import Ca, Cert


class TestAdmin(TestPkiMixin, TestAdminMixin,
                TestOrganizationMixin, TestCase):
    ca_model = Ca
    cert_model = Cert
    operator_permission_filters = [
        {'codename__endswith': 'ca'},
        {'codename__endswith': 'cert'},
    ]

    def _create_multitenancy_test_env(self, cert=False):
        org1 = self._create_org(name='test1org')
        org2 = self._create_org(name='test2org')
        inactive = self._create_org(name='inactive-org', is_active=False)
        operator = self._create_operator(organizations=[org1, inactive])
        ca1 = self._create_ca(name='ca1', organization=org1)
        ca2 = self._create_ca(name='ca2', organization=org2)
        ca_shared = self._create_ca(name='ca-shared', organization=None)
        ca_inactive = self._create_ca(name='ca-inactive', organization=inactive)
        data = dict(ca1=ca1, ca2=ca2, ca_inactive=ca_inactive, ca_shared=ca_shared,
                    org1=org1, org2=org2, inactive=inactive,
                    operator=operator)
        if cert:
            cert1 = self._create_cert(name='cert1', ca=ca1, organization=org1)
            cert2 = self._create_cert(name='cert2', ca=ca2, organization=org2)
            cert_shared = self._create_cert(name='cert-shared',
                                            ca=ca_shared,
                                            organization=None)
            cert_inactive = self._create_cert(name='cert-inactive',
                                              ca=ca_inactive,
                                              organization=inactive)
            data.update(dict(cert1=cert1, cert_shared=cert_shared,
                             cert2=cert2, cert_inactive=cert_inactive))
        return data

    def test_ca_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse('admin:pki_ca_changelist'),
            visible=[data['ca1'].name, data['org1'].name],
            hidden=[data['ca2'].name, data['org2'].name,
                    data['ca_inactive'].name,
                    data['ca_shared'].name]
        )

    def test_ca_organization_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse('admin:pki_ca_add'),
            visible=[data['org1'].name],
            hidden=[data['org2'].name, data['inactive']],
            select_widget=True
        )

    def test_cert_queryset(self):
        data = self._create_multitenancy_test_env(cert=True)
        self._test_multitenant_admin(
            url=reverse('admin:pki_cert_changelist'),
            visible=[data['cert1'].name,
                     data['org1'].name],
            hidden=[data['cert2'].name,
                    data['org2'].name,
                    data['cert_inactive'].name,
                    data['cert_shared'].name]
        )

    def test_cert_organization_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse('admin:pki_cert_add'),
            visible=[data['org1'].name],
            hidden=[data['org2'].name, data['inactive']],
            select_widget=True
        )

    def test_cert_ca_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse('admin:pki_cert_add'),
            visible=[data['ca1'].name, data['ca_shared'].name],
            hidden=[data['ca2'].name, data['ca_inactive'].name],
            select_widget=True
        )

    def test_cert_changeform_200(self):
        org = self._create_org(name='test-org')
        self._create_operator(organizations=[org])
        self._login(username='operator', password='tester')
        ca = self._create_ca(name='ca', organization=org)
        cert = self._create_cert(name='cert', ca=ca, organization=org)
        url = reverse('admin:pki_cert_change', args=[cert.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_changelist_recover_deleted_button(self):
        self._create_multitenancy_test_env()
        self._test_changelist_recover_deleted('pki', 'ca')
        self._test_changelist_recover_deleted('pki', 'cert')

    def test_recoverlist_operator_403(self):
        self._create_multitenancy_test_env()
        self._test_recoverlist_operator_403('pki', 'ca')
        self._test_recoverlist_operator_403('pki', 'cert')
