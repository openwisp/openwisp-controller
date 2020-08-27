import json

from django.test import TestCase
from django.urls import reverse
from swapper import load_model

from ...config.tests.test_admin import TestAdmin as TestConfigAdmin
from ...tests.utils import TestAdminMixin
from ..connectors.ssh import Ssh
from ..widgets import CredentialsSchemaWidget
from .utils import CreateConnectionsMixin

Template = load_model('config', 'Template')
Config = load_model('config', 'Config')
Device = load_model('config', 'Device')
Credentials = load_model('connection', 'Credentials')
DeviceConnection = load_model('connection', 'DeviceConnection')


class TestAdmin(TestAdminMixin, CreateConnectionsMixin, TestCase):
    config_app_label = 'config'
    app_label = 'connection'
    operator_permission_filters = [
        {'codename__endswith': 'config'},
        {'codename__endswith': 'device'},
        {'codename__endswith': 'template'},
        {'codename__endswith': 'connection'},
        {'codename__endswith': 'credentials'},
        {'codename__endswith': 'device_connection'},
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
        data = dict(
            cred1=cred1,
            cred2=cred2,
            cred3_inactive=cred3,
            dc1=dc1,
            dc2=dc2,
            dc3_inactive=dc3,
            org1=org1,
            org2=org2,
            inactive=inactive,
            operator=operator,
        )
        return data

    def test_credentials_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_credentials_changelist'),
            visible=[data['cred1'].name, data['org1'].name],
            hidden=[data['cred2'].name, data['org2'].name, data['cred3_inactive'].name],
        )

    def test_credentials_organization_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_credentials_add'),
            visible=[data['org1'].name],
            hidden=[data['org2'].name, data['inactive']],
            select_widget=True,
        )

    def test_connection_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_credentials_changelist'),
            visible=[data['dc1'].credentials.name, data['org1'].name],
            hidden=[
                data['dc2'].credentials.name,
                data['org2'].name,
                data['dc3_inactive'].credentials.name,
            ],
        )

    def test_connection_credentials_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.config_app_label}_device_add'),
            visible=[str(data['cred1'].name) + str(' (SSH)')],
            hidden=[str(data['cred2'].name) + str(' (SSH)'), data['cred3_inactive']],
            select_widget=True,
        )

    def test_credentials_jsonschema_widget_presence(self):
        url = reverse(f'admin:{self.app_label}_credentials_add')
        schema_url = reverse(CredentialsSchemaWidget.schema_view_name)
        expected = f'<script>django._jsonSchemaWidgetUrl = "{schema_url}";</script>'
        self._login()
        response = self.client.get(url)
        self.assertContains(response, expected)

    def test_credentials_jsonschema_widget_media(self):
        widget = CredentialsSchemaWidget()
        html = widget.media.render()
        expected_list = [
            'admin/js/jquery.init.js',
            'connection/js/credentials.js',
            'connection/css/credentials.css',
        ]
        for expected in expected_list:
            self.assertIn(expected, html)

    def test_credentials_jsonschema_view(self):
        url = reverse(CredentialsSchemaWidget.schema_view_name)
        self._login()
        response = self.client.get(url)
        ssh_schema = json.dumps(Ssh.schema)
        self.assertIn(ssh_schema, response.content.decode('utf8'))


del TestConfigAdmin
