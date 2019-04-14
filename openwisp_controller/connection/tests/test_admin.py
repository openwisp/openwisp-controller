import json

from django.test import TestCase
from django.urls import reverse

from ...config.models import Template
from ...config.tests.test_admin import TestAdmin as TestConfigAdmin
from ...tests.utils import TestAdminMixin
from .. import settings as app_settings
from ..models import Credentials, DeviceConnection, DeviceIp
from .base import CreateConnectionsMixin, SshServerMixin


class TestAdmin(TestAdminMixin, CreateConnectionsMixin,
                SshServerMixin, TestCase):
    template_model = Template
    credentials_model = Credentials
    deviceip_model = DeviceIp
    connection_model = DeviceConnection
    operator_permission_filters = [
        {'codename__endswith': 'config'},
        {'codename__endswith': 'device'},
        {'codename__endswith': 'template'},
        {'codename__endswith': 'connection'},
        {'codename__endswith': 'credentials'},
        {'codename__endswith': 'device_connection'},
        {'codename__endswith': 'device_ip'},
    ]
    _device_params = TestConfigAdmin._device_params.copy()

    def _get_device_params(self, org):
        p = self._device_params.copy()
        p['organization'] = org.pk
        return p

    def test_device_config_update(self):
        org1 = self._create_org(name='org1')
        cred = self._create_credentials_with_key(organization=org1, port=self.ssh_server.port)
        device = self._create_device(organization=org1)
        update_strategy = app_settings.UPDATE_STRATEGIES[0][0]
        c = self._create_config(device=device)
        dc = self._create_device_connection(device=device,
                                            credentials=cred,
                                            update_strategy=update_strategy)
        self._create_device_ip(device=device,
                               address=self.ssh_server.host)
        uid = self.ssh_server.users
        config = json.dumps({
            'interfaces': [
                {
                    'name': 'eth0',
                    'type': 'ethernet',
                    'addresses': [
                        {
                            'family': 'ipv4',
                            'proto': 'dhcp'
                        }
                    ]
                }
            ]
        })
        c.config = config
        dc.update_config()
        self.ssh_server.client(*uid).exec_command('/etc/init.d/openwisp_config restart')
        self.assertEqual(device.status, 'applied')

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
            visible=[data['cred1'].name + ' (SSH)'],
            hidden=[data['cred2'].name + ' (SSH)', data['cred3_inactive']],
            select_widget=True
        )
