import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from swapper import load_model

from ... import settings as module_settings
from ...config.tests.test_admin import TestAdmin as TestConfigAdmin
from ...tests import _get_updated_templates_settings
from ...tests.utils import TestAdminMixin
from ..connectors.ssh import Ssh
from ..widgets import CredentialsSchemaWidget
from .utils import CreateConnectionsMixin

Template = load_model('config', 'Template')
Config = load_model('config', 'Config')
Device = load_model('config', 'Device')
Credentials = load_model('connection', 'Credentials')
DeviceConnection = load_model('connection', 'DeviceConnection')
Command = load_model('connection', 'Command')


class TestConnectionAdmin(TestAdminMixin, CreateConnectionsMixin, TestCase):
    config_app_label = 'config'
    app_label = 'connection'
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
        administrator = self._create_administrator(organizations=[org1, inactive])
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
            administrator=administrator,
        )
        return data

    def test_credentials_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_credentials_changelist'),
            visible=[data['cred1'].name, data['org1'].name],
            hidden=[data['cred2'].name, data['org2'].name, data['cred3_inactive'].name],
            administrator=True,
        )

    def test_credentials_organization_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_credentials_add'),
            visible=[data['org1'].name],
            hidden=[data['org2'].name, data['inactive']],
            select_widget=True,
            administrator=True,
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
            administrator=True,
        )

    def test_connection_credentials_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.config_app_label}_device_add'),
            visible=[str(data['cred1'].name) + str(' (SSH)')],
            hidden=[str(data['cred2'].name) + str(' (SSH)'), data['cred3_inactive']],
            select_widget=True,
        )

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

    def test_admin_menu_groups(self):
        # Test menu group (openwisp-utils menu group) for Credentials model
        self.client.force_login(self._get_admin())
        models = ['credentials']
        response = self.client.get(reverse('admin:index'))
        for model in models:
            with self.subTest(f'test menu group link for {model} model'):
                url = reverse(f'admin:{self.app_label}_{model}_changelist')
                self.assertContains(response, f' class="mg-link" href="{url}"')


class TestCommandInlines(TestAdminMixin, CreateConnectionsMixin, TestCase):
    config_app_label = 'config'

    def setUp(self):
        self.admin = self._get_admin()
        self.client.force_login(self.admin)
        self.device_connection = self._create_device_connection()
        self.device = self.device_connection.device

    def _create_custom_command(self):
        return Command.objects.create(
            type='custom', input={'command': 'echo hello'}, device=self.device
        )

    def test_command_inline(self):
        url = reverse(
            f'admin:{self.config_app_label}_device_change', args=(self.device.id,)
        )

        with self.subTest(
            'Test "Recent Commands" not shown for a device without commands'
        ):
            response = self.client.get(url)
            self.assertNotContains(response, 'Recent Commands')

        with self.subTest('Test "Recent Commands" shown for a device having commands'):
            self._create_custom_command()
            response = self.client.get(url)
            self.assertContains(response, 'Recent Commands')

    def test_command_writable_inline(self):
        url = reverse(
            f'admin:{self.config_app_label}_device_change', args=(self.device.id,)
        )

        with self.subTest(
            'Test add command form is present for a device without commands'
        ):
            response = self.client.get(url)
            self.assertContains(response, 'id_command_set')

        with self.subTest(
            'Test add command form is present for a device having commands'
        ):
            self._create_custom_command()
            response = self.client.get(url)
            self.assertContains(response, 'id_command_set')

    def test_commands_schema_view(self):
        url = reverse(
            f'admin:{Command._meta.app_label}_{Command._meta.model_name}_schema'
        )
        response = self.client.get(url)
        result = json.loads(response.content)
        self.assertIn('custom', result)
        self.assertIn('change_password', result)
        self.assertIn('reboot', result)

    @patch.object(
        module_settings,
        'OPENWISP_CONTROLLER_API_HOST',
        'https://example.com',
    )
    def test_notification_host_setting(self, ctx_processors=[]):
        url = reverse(
            f'admin:{self.config_app_label}_device_change', args=(self.device.id,)
        )
        with override_settings(
            TEMPLATES=_get_updated_templates_settings(ctx_processors)
        ):
            response = self.client.get(url)
            self.assertContains(response, 'https://example.com')
            self.assertNotContains(response, 'owControllerApiHost = window.location')


del TestConfigAdmin
