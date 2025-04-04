import os
from unittest import mock

from django.conf import settings
from django.test import TestCase
from paramiko.ssh_exception import AuthenticationException
from swapper import load_model

from ..connectors.ssh import logger as ssh_logger
from .utils import CreateConnectionsMixin, SshServer

Config = load_model('config', 'Config')
Device = load_model('config', 'Device')
Credentials = load_model('connection', 'Credentials')
DeviceConnection = load_model('connection', 'DeviceConnection')


class TestSsh(CreateConnectionsMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mock_ssh_server = SshServer(
            {'root': cls._TEST_RSA_PRIVATE_KEY_PATH}
        ).__enter__()
        cls.ssh_server.port = cls.mock_ssh_server.port

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.mock_ssh_server.__exit__()

    @mock.patch.object(ssh_logger, 'debug')
    def test_connection_connect(self, mocked_debug):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connect()
        self.assertTrue(dc.is_working)
        with mock.patch('logging.Logger.info') as mocked_logger:
            dc.connector_instance.exec_command('echo test')
        mocked_logger.assert_has_calls(
            [mock.call('Executing command: echo test'), mock.call('test\n')]
        )

    @mock.patch('paramiko.SSHClient.close')
    def test_connection_connect_auth_failure(self, mocked_ssh_close):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        auth_failed = AuthenticationException('Authentication failed.')
        with mock.patch(
            'paramiko.SSHClient.connect', side_effect=auth_failed
        ) as mocked_connect:
            dc.connect()
        self.assertEqual(mocked_connect.call_count, 2)
        self.assertFalse(dc.is_working)
        self.assertEqual(mocked_ssh_close.call_count, 2)
        self.assertNotIn('disabled_algorithms', mocked_connect.mock_calls[0].kwargs)
        self.assertIn('disabled_algorithms', mocked_connect.mock_calls[1].kwargs)

    @mock.patch.object(ssh_logger, 'info')
    @mock.patch.object(ssh_logger, 'debug')
    def test_connection_failed_command(self, mocked_debug, mocked_info):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connector_instance.connect()
        with self.assertRaises(Exception):
            dc.connector_instance.exec_command('wrongcommand')
        mocked_info.assert_has_calls(
            [
                mock.call('Unexpected exit code: 127'),
            ]
        )

    @mock.patch.object(ssh_logger, 'info')
    @mock.patch.object(ssh_logger, 'debug')
    def test_connection_failed_command_suppressed_output(
        self, mocked_debug, mocked_info
    ):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connector_instance.connect()
        with self.assertRaises(Exception) as ctx:
            dc.connector_instance.exec_command(
                'rm /thisfilesurelydoesnotexist 2> /dev/null'
            )
        log_message = 'Unexpected exit code: 1'
        mocked_info.assert_has_calls([mock.call(log_message)])
        self.assertEqual(str(ctx.exception), log_message)

    @mock.patch('scp.SCPClient.putfo')
    def test_connection_upload(self, putfo_mocked):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connector_instance.connect()
        # needs a binary file to test all lines
        fl = open(os.path.join(settings.BASE_DIR, '../media/floorplan.jpg'), 'rb')
        dc.connector_instance.upload(fl, '/tmp/test')
        putfo_mocked.assert_called_once()

    def test_connection_reconnect(self):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connect()
        with mock.patch('paramiko.SSHClient.connect') as mocked_paramiko:
            dc.connect()
        mocked_paramiko.assert_not_called()

    def test_is_connected_new_connection(self):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        self.assertEqual(dc.connector_instance.is_connected, False)
