import os

import paramiko
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase
from mockssh import Server as SshServer
from openwisp_controller.config.models import Config, Device
from openwisp_controller.config.tests import CreateConfigTemplateMixin

from openwisp_users.tests.utils import TestOrganizationMixin

from ..models import Credentials, DeviceConnection, DeviceIp


class TestConnectionMixin(CreateConfigTemplateMixin, TestOrganizationMixin):
    device_model = Device
    config_model = Config
    _TEST_RSA_KEY_PATH = os.path.join(settings.BASE_DIR, 'test-key.rsa')
    with open(_TEST_RSA_KEY_PATH, 'r') as f:
        _SSH_PRIVATE_KEY = f.read()

    @classmethod
    def setUpClass(cls):
        cls.ssh_server = SshServer({'root': cls._TEST_RSA_KEY_PATH})
        cls.ssh_server.__enter__()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.ssh_server.__exit__()
        except OSError:
            pass

    def _create_credentials(self, **kwargs):
        opts = dict(name='Test credentials',
                    connector=Credentials.CONNECTOR_CHOICES[0][0],
                    params={'username': 'root',
                            'password': 'password',
                            'port': 22})
        opts.update(kwargs)
        if 'organization' not in opts:
            opts['organization'] = self._create_org()
        c = Credentials(**opts)
        c.full_clean()
        c.save()
        return c

    def _create_credentials_with_key(self, username='root', port=22, **kwargs):
        opts = dict(name='Test SSH Key',
                    params={'username': username,
                            'key': self._SSH_PRIVATE_KEY,
                            'port': port})
        return self._create_credentials(**opts)

    def _create_device_connection(self, **kwargs):
        opts = dict(enabled=True,
                    params={})
        opts.update(kwargs)
        if 'credentials' not in opts:
            opts['credentials'] = self._create_credentials()
        org = opts['credentials'].organization
        if 'device' not in opts:
            opts['device'] = self._create_device(organization=org)
            self._create_config(device=opts['device'])
        dc = DeviceConnection(**opts)
        dc.full_clean()
        dc.save()
        return dc

    def _create_device_ip(self, **kwargs):
        opts = dict(address='10.40.0.1',
                    priority=1)
        opts.update(kwargs)
        if 'device' not in opts:
            dc = self._create_device_connection()
            opts['device'] = dc.device
        ip = DeviceIp(**opts)
        ip.full_clean()
        ip.save()
        return ip


class TestModels(TestConnectionMixin, TestCase):
    def test_connection_str(self):
        c = Credentials(name='Dev Key', connector=Credentials.CONNECTOR_CHOICES[0][0])
        self.assertIn(c.name, str(c))
        self.assertIn(c.get_connector_display(), str(c))

    def test_deviceip_str(self):
        di = DeviceIp(address='10.40.0.1')
        self.assertIn(di.address, str(di))

    def test_device_connection_get_params(self):
        dc = self._create_device_connection()
        self.assertEqual(dc.get_params(), dc.credentials.params)
        dc.params = {'port': 2400}
        self.assertEqual(dc.get_params()['port'], 2400)
        self.assertEqual(dc.get_params()['username'], 'root')

    def test_device_connection_auto_update_strategy(self):
        dc = self._create_device_connection()
        self.assertEqual(dc.update_strategy, dc.UPDATE_STRATEGY_CHOICES[0][0])

    def test_device_connection_auto_update_strategy_key_error(self):
        orig_strategy = DeviceConnection.UPDATE_STRATEGY_CHOICES
        orig_mapping = DeviceConnection.CONFIG_BACKEND_MAPPING
        DeviceConnection.UPDATE_STRATEGY_CHOICES = (('meddle', 'meddle'),)
        DeviceConnection.CONFIG_BACKEND_MAPPING = {'wrong': 'wrong'}
        try:
            self._create_device_connection()
        except ValidationError:
            failed = False
        else:
            failed = True
        # restore
        DeviceConnection.UPDATE_STRATEGY_CHOICES = orig_strategy
        DeviceConnection.CONFIG_BACKEND_MAPPING = orig_mapping
        if failed:
            self.fail('ValidationError not raised')

    def test_device_connection_auto_update_strategy_missing_config(self):
        device = self._create_device(organization=self._create_org())
        self.assertFalse(hasattr(device, 'config'))
        try:
            self._create_device_connection(device=device)
        except ValidationError as e:
                self.assertIn('inferred from', str(e))
        else:
            self.fail('ValidationError not raised')

    def test_device_connection_connector_instance(self):
        dc = self._create_device_connection()
        self.assertIsInstance(dc.connector_instance, dc.connector_class)

    def test_device_connection_ssh_key_param(self):
        ckey = self._create_credentials_with_key()
        dc = self._create_device_connection(credentials=ckey)
        self.assertIn('pkey', dc.connector_instance._params)
        self.assertIsInstance(dc.connector_instance._params['pkey'],
                              paramiko.rsakey.RSAKey)
        self.assertNotIn('key', dc.connector_instance._params)

    def test_ssh_connect(self):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        self._create_device_ip(address=self.ssh_server.host,
                               device=dc.device)
        dc.connect()
        self.assertTrue(dc.is_working)
        self.assertIsNotNone(dc.last_attempt)
        self.assertEqual(dc.failure_reason, '')
        try:
            dc.disconnect()
        except OSError:
            pass

    def test_ssh_connect_failure(self):
        ckey = self._create_credentials_with_key(username='wrong',
                                                 port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        self._create_device_ip(address=self.ssh_server.host,
                               device=dc.device)
        dc.connect()
        self.assertEqual(dc.is_working, False)
        self.assertIsNotNone(dc.last_attempt)
        self.assertEqual(dc.failure_reason, 'Authentication failed.')

    def test_credentials_schema(self):
        # unrecognized parameter
        try:
            self._create_credentials(params={
                'username': 'root',
                'password': 'password',
                'unrecognized': True
            })
        except ValidationError as e:
            self.assertIn('params', e.message_dict)
        else:
            self.fail('ValidationError not raised')
        # missing password or key
        try:
            self._create_credentials(params={
                'username': 'root',
                'port': 22
            })
        except ValidationError as e:
            self.assertIn('params', e.message_dict)
        else:
            self.fail('ValidationError not raised')

    def test_device_connection_schema(self):
        # unrecognized parameter
        try:
            self._create_device_connection(params={
                'username': 'root',
                'password': 'password',
                'unrecognized': True
            })
        except ValidationError as e:
            self.assertIn('params', e.message_dict)
        else:
            self.fail('ValidationError not raised')
