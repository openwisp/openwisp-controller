import paramiko
from django.core.exceptions import ValidationError
from django.test import TestCase

from .. import settings as app_settings
from ..models import Credentials, DeviceIp
from ..utils import get_interfaces
from .base import CreateConnectionsMixin, SshServerMixin


class TestModels(SshServerMixin, CreateConnectionsMixin, TestCase):
    def test_connection_str(self):
        c = Credentials(name='Dev Key', connector=app_settings.CONNECTORS[0][0])
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
        self.assertEqual(dc.update_strategy, app_settings.UPDATE_STRATEGIES[0][0])

    def test_device_connection_auto_update_strategy_key_error(self):
        orig_strategy = app_settings.UPDATE_STRATEGIES
        orig_mapping = app_settings.CONFIG_UPDATE_MAPPING
        app_settings.UPDATE_STRATEGIES = (('meddle', 'meddle'),)
        app_settings.CONFIG_UPDATE_MAPPING = {'wrong': 'wrong'}
        try:
            self._create_device_connection()
        except ValidationError:
            failed = False
        else:
            failed = True
        # restore
        app_settings.UPDATE_STRATEGIES = orig_strategy
        app_settings.CONFIG_UPDATE_MAPPING = orig_mapping
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
        self.assertIn('pkey', dc.connector_instance.params)
        self.assertIsInstance(dc.connector_instance.params['pkey'],
                              paramiko.rsakey.RSAKey)
        self.assertNotIn('key', dc.connector_instance.params)

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

    def _prepare_address_list_test(self, addresses,
                                   last_ip=None,
                                   management_ip=None):
        update_strategy = app_settings.UPDATE_STRATEGIES[0][0]
        device = self._create_device(organization=self._create_org(),
                                     last_ip=last_ip,
                                     management_ip=management_ip)
        dc = self._create_device_connection(device=device,
                                            update_strategy=update_strategy)
        for index, address in enumerate(addresses):
            self._create_device_ip(device=device,
                                   address=address,
                                   priority=index + 1)
        return dc

    def test_address_list(self):
        dc = self._prepare_address_list_test(['10.40.0.1', '192.168.40.1'])
        self.assertEqual(dc.get_addresses(), [
            '10.40.0.1',
            '192.168.40.1'
        ])

    def test_address_list_with_device_ip(self):
        dc = self._prepare_address_list_test(
            ['192.168.40.1'],
            management_ip='10.0.0.2',
            last_ip='84.32.46.153',
        )
        self.assertEqual(dc.get_addresses(), [
            '192.168.40.1',
            '10.0.0.2',
            '84.32.46.153'
        ])

    def test_address_list_link_local_ip(self):
        ipv6_linklocal = 'fe80::2dae:a0d4:94da:7f61'
        dc = self._prepare_address_list_test([ipv6_linklocal])
        address_list = dc.get_addresses()
        interfaces = get_interfaces()
        self.assertEqual(len(address_list), len(interfaces))
        self.assertIn(ipv6_linklocal, address_list[0])

    def test_device_connection_credential_org_validation(self):
        dc = self._create_device_connection()
        shared = self._create_credentials(name='cred-shared',
                                          organization=None)
        dc.credentials = shared
        dc.full_clean()
        # ensure credentials of other orgs aren't accepted
        org2 = self._create_org(name='org2')
        cred2 = self._create_credentials(name='cred2',
                                         organization=org2)
        try:
            dc.credentials = cred2
            dc.full_clean()
        except ValidationError as e:
            self.assertIn('credentials', e.message_dict)
        else:
            self.fail('ValidationError not raised')
