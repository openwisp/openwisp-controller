from django.test import TestCase
from django.urls import reverse

from ...config.models import Template
from ...config.tests.test_admin import TestAdmin as TestConfigAdmin
from ...tests.utils import TestAdminMixin
from ..models import Credentials, DeviceConnection
from .base import CreateConnectionsMixin


class TestAdmin(TestAdminMixin, CreateConnectionsMixin, TestCase):
    template_model = Template
    credentials_model = Credentials
    connection_model = DeviceConnection
    operator_permission_filters = [
        {'codename__endswith': 'config'},
        {'codename__endswith': 'device'},
        {'codename__endswith': 'template'},
        {'codename__endswith': 'connection'},
        {'codename__endswith': 'credentials'},
        {'codename__endswith': 'device_connection'}
    ]
    _device_params = TestConfigAdmin._device_params.copy()

    def _get_device_params(self, org):
        p = self._device_params.copy()
        p['organization'] = org.pk
        return p

    def _create_multitenancy_test_env(self):
        org1 = self._create_org(name='test1org')
        org2 = self._create_org(name='test2org')
        inactive = self._create_org(name='inactive-org', is_active=False)
        operator = self._create_operator(organizations=[org1, inactive])
        cred1 = self._create_credentials(organization=org1, name='test1cred')
        cred2 = self._create_credentials(organization=org2, name='test2cred')
        cred3 = self._create_credentials(organization=inactive, name='test3cred')
        dc1 = self._create_device_connection(credentials=cred1)
        dc2 = self._create_device_connection(credentials=cred2)
        dc3 = self._create_device_connection(credentials=cred3)
        data = dict(cred1=cred1, cred2=cred2, cred3_inactive=cred3,
                    dc1=dc1, dc2=dc2, dc3_inactive=dc3,
                    org1=org1, org2=org2, inactive=inactive,
                    operator=operator)
        return data

    def test_credentials_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse('admin:connection_credentials_changelist'),
            visible=[data['cred1'].name, data['org1'].name],
            hidden=[data['cred2'].name, data['org2'].name,
                    data['cred3_inactive'].name]
        )

    def test_credentials_organization_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse('admin:connection_credentials_add'),
            visible=[data['org1'].name],
            hidden=[data['org2'].name, data['inactive']],
            select_widget=True
        )

    def test_connection_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse('admin:connection_credentials_changelist'),
            visible=[data['dc1'].credentials.name, data['org1'].name],
            hidden=[data['dc2'].credentials.name, data['org2'].name,
                    data['dc3_inactive'].credentials.name]
        )

    def test_connection_credentials_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse('admin:config_device_add'),
            visible=[str(data['cred1'].name) + str(" (SSH)")],
            hidden=[str(data['cred2'].name) + str(" (SSH)"), data['cred3_inactive']],
            select_widget=True
        )
