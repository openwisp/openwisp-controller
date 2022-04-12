import socket
from unittest import mock

import paramiko
from django.contrib.auth.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.utils.module_loading import import_string
from swapper import load_model

from openwisp_utils.tests import capture_any_output, catch_signal

from .. import settings as app_settings
from ..apps import _TASK_NAME
from ..commands import register_command, unregister_command
from ..signals import is_working_changed
from ..tasks import update_config
from .utils import CreateConnectionsMixin

Config = load_model('config', 'Config')
Device = load_model('config', 'Device')
Credentials = load_model('connection', 'Credentials')
DeviceConnection = load_model('connection', 'DeviceConnection')
Group = load_model('openwisp_users', 'Group')
Organization = load_model('openwisp_users', 'Organization')
Command = load_model('connection', 'Command')

_connect_path = 'paramiko.SSHClient.connect'
_exec_command_path = 'paramiko.SSHClient.exec_command'


class BaseTestModels(CreateConnectionsMixin):
    app_label = 'connection'

    def _exec_command_return_value(
        self, stdin='', stdout='mocked', stderr='', exit_code=0
    ):
        stdin_ = mock.Mock()
        stdout_ = mock.Mock()
        stderr_ = mock.Mock()
        stdin_.read().decode.return_value = stdin
        stdout_.read().decode.return_value = stdout
        stdout_.channel.recv_exit_status.return_value = exit_code
        stderr_.read().decode.return_value = stderr
        return (stdin_, stdout_, stderr_)


class TestModels(BaseTestModels, TestCase):
    def test_connection_str(self):
        c = Credentials(name='Dev Key', connector=app_settings.CONNECTORS[0][0])
        self.assertIn(c.name, str(c))
        self.assertIn(c.get_connector_display(), str(c))

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
        device = self._create_device(organization=self._get_org())
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

    def test_device_connection_ssh_rsa_key_param(self):
        ckey = self._create_credentials_with_key()
        dc = self._create_device_connection(credentials=ckey)
        self.assertIn('pkey', dc.connector_instance.params)
        self.assertIsInstance(
            dc.connector_instance.params['pkey'], paramiko.rsakey.RSAKey
        )
        self.assertNotIn('key', dc.connector_instance.params)

    def test_device_connection_ssh_ed22519_key_param(self):
        ckey = self._create_credentials_with_ed_key()
        dc = self._create_device_connection(credentials=ckey)
        self.assertIn('pkey', dc.connector_instance.params)
        self.assertIsInstance(
            dc.connector_instance.params['pkey'], paramiko.ed25519key.Ed25519Key
        )
        self.assertNotIn('key', dc.connector_instance.params)

    def test_credentials_invalid_ssh_key(self):
        invalid_keys = [
            """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABsQAAAAdzc2gtZH
NzAAAAgQCPS4iiaXzTs+VST1o1w6oU2c0IBIAjaM/gmdpuj45F5KKbNuoHxDHxXS7KagML
Lg6Lv7B4I290HR9S2aUVpSW1JhswO28LJz5+zVAIpSjp+aCGv0GqQdFKcZ9gUejZcg1ZTK
OTVDTfojbraBBJDQVJH8IfoPTuQ8R+SEoAgM8euwAAABUAxKPeMdsQKah4zJNjiMkUi4gN
5FkAAACACE33nYpHu+O4naJMIIH62L7i2yKWkccPMk32pq1Iin9dOIjVAUv7U/HKovqqyt
kzvhjCHIZsZBPlR319gw//ywRUbvSbDBZWV16SOMFJNyH8Wcx73FpjokxtTTu83DQMnx37
KpEdLBD3I1BpjWlOY+Hpu4lwsnPWAoNsp4m78dkAAACACFnPy97iwr1ZuimrjcK7aRAOBf
g2gDpb4UKbEIp/kCFgjNhDEirIJrN3syuMLBKjEQ/BaSmAJcOZchclKb9YaJIElljs2ran
C1/KFzpov5rdj4s+asafCNix2ptkj4GKGSQgeV5dR2NK/b7t4B2Wdy6U0vaM6/IWQhqvvM
+mMY4AAAHom2XawZtl2sEAAAAHc3NoLWRzcwAAAIEAj0uIoml807PlUk9aNcOqFNnNCASA
I2jP4Jnabo+OReSimzbqB8Qx8V0uymoDCy4Oi7+weCNvdB0fUtmlFaUltSYbMDtvCyc+fs
1QCKUo6fmghr9BqkHRSnGfYFHo2XINWUyjk1Q036I262gQSQ0FSR/CH6D07kPEfkhKAIDP
HrsAAAAVAMSj3jHbECmoeMyTY4jJFIuIDeRZAAAAgAhN952KR7vjuJ2iTCCB+ti+4tsilp
HHDzJN9qatSIp/XTiI1QFL+1PxyqL6qsrZM74YwhyGbGQT5Ud9fYMP/8sEVG70mwwWVlde
kjjBSTch/FnMe9xaY6JMbU07vNw0DJ8d+yqRHSwQ9yNQaY1pTmPh6buJcLJz1gKDbKeJu/
HZAAAAgAhZz8ve4sK9Wbopq43Cu2kQDgX4NoA6W+FCmxCKf5AhYIzYQxIqyCazd7MrjCwS
oxEPwWkpgCXDmXIXJSm/WGiSBJZY7Nq2pwtfyhc6aL+a3Y+LPmrGnwjYsdqbZI+BihkkIH
leXUdjSv2+7eAdlnculNL2jOvyFkIar7zPpjGOAAAAFHFcD3oAPq5orH1/9tdihL2Gn4Iu
AAAADG5lbWVzaXNAZW52eQECAwQFBgc=
-----END OPENSSH PRIVATE KEY-----""",
            """+mMY4AAAHom2XawZtl2sEAAAAHc3NoLWRzcwAAAIEAj0uIoml807PlUk9aNcOqFNnNCASA
leXUdjSv2+7eAdlnculNL2jOvyFkIar7zPpjGOAAAAFHFcD3oAPq5orH1/9tdihL2Gn4Iu
HZAAAAgAhZz8ve4sK9Wbopq43Cu2kQDgX4NoA6W+FCmxCKf5AhYIzYQxIqyCazd7MrjCwS""",
        ]
        for invalid_key in invalid_keys:
            opts = dict(
                name='Test SSH Key',
                params={'username': 'root', 'key': invalid_key, 'port': 22},
            )
            with self.subTest(f'Testing key {invalid_key}'):
                with self.assertRaises(ValidationError) as ctx:
                    self._create_credentials(**opts)
                self.assertIn('params', ctx.exception.message_dict)
                self.assertIn(
                    'Unrecognized or unsupported SSH key algorithm',
                    str(ctx.exception.message_dict['params']),
                )

    @mock.patch(_connect_path)
    def test_ssh_connect(self, mocked_connect):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connect()
        mocked_connect.assert_called_once()
        self.assertTrue(dc.is_working)
        self.assertIsNotNone(dc.last_attempt)
        self.assertEqual(dc.failure_reason, '')
        dc.disconnect()

    def test_ssh_connect_failure(self):
        ckey = self._create_credentials_with_key(
            username='wrong', port=self.ssh_server.port
        )
        dc = self._create_device_connection(credentials=ckey)
        dc.device.last_ip = None
        dc.device.save()
        with mock.patch(_connect_path) as mocked_connect:
            mocked_connect.side_effect = Exception('Authentication failed.')
            dc.connect()
            mocked_connect.assert_called_once()
        self.assertEqual(dc.is_working, False)
        self.assertIsNotNone(dc.last_attempt)
        self.assertEqual(dc.failure_reason, 'Authentication failed.')

    def test_credentials_schema(self):
        # unrecognized parameter
        try:
            self._create_credentials(
                params={
                    'username': 'root',
                    'password': 'password',
                    'unrecognized': True,
                }
            )
        except ValidationError as e:
            self.assertIn('params', e.message_dict)
        else:
            self.fail('ValidationError not raised')
        # missing password or key
        try:
            self._create_credentials(params={'username': 'root', 'port': 22})
        except ValidationError as e:
            self.assertIn('params', e.message_dict)
        else:
            self.fail('ValidationError not raised')

    def test_credentials_connection_missing(self):
        with self.assertRaises(ValidationError) as e:
            c = Credentials(
                name='Test credentials',
                connector=None,
                params={'username': 'root', 'password': 'password', 'port': 22},
                organization=self._get_org(),
            )
            c.full_clean()
            self.assertIn('connector', e.message_dict)

    def test_device_connection_schema(self):
        # unrecognized parameter
        try:
            self._create_device_connection(
                params={
                    'username': 'root',
                    'password': 'password',
                    'unrecognized': True,
                }
            )
        except ValidationError as e:
            self.assertIn('params', e.message_dict)
        else:
            self.fail('ValidationError not raised')

    def _prepare_address_list_test(self, last_ip=None, management_ip=None):
        update_strategy = app_settings.UPDATE_STRATEGIES[0][0]
        device = self._create_device(
            organization=self._get_org(), last_ip=last_ip, management_ip=management_ip
        )
        dc = self._create_device_connection(
            device=device, update_strategy=update_strategy
        )
        return dc

    def test_address_list(self):
        dc = self._prepare_address_list_test()
        self.assertEqual(dc.get_addresses(), [])

    def test_address_list_with_device_ip(self):
        dc = self._prepare_address_list_test(
            management_ip='10.0.0.2', last_ip='84.32.46.153'
        )
        self.assertEqual(dc.get_addresses(), ['10.0.0.2', '84.32.46.153'])

    def test_device_connection_credential_org_validation(self):
        dc = self._create_device_connection()
        shared = self._create_credentials(name='cred-shared', organization=None)
        dc.credentials = shared
        dc.full_clean()
        # ensure credentials of other orgs aren't accepted
        org2 = self._create_org(name='org2')
        cred2 = self._create_credentials(name='cred2', organization=org2)
        try:
            dc.credentials = cred2
            dc.full_clean()
        except ValidationError as e:
            self.assertIn('credentials', e.message_dict)
        else:
            self.fail('ValidationError not raised')

    def test_auto_add_to_new_device(self):
        c = self._create_credentials(auto_add=True, organization=None)
        self._create_credentials(name='cred2', auto_add=False, organization=None)
        d = self._create_device(organization=Organization.objects.first())
        self._create_config(device=d)
        d.refresh_from_db()
        self.assertEqual(d.deviceconnection_set.count(), 1)
        self.assertEqual(d.deviceconnection_set.first().credentials, c)

    def test_auto_add_device_missing_config(self):
        org = Organization.objects.first()
        self._create_device(organization=org)
        self._create_credentials(auto_add=True, organization=None)
        self.assertEqual(Credentials.objects.count(), 1)

    @capture_any_output()
    @mock.patch(_connect_path)
    def test_ssh_exec_exit_code(self, *args):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connector_instance.connect()
        with mock.patch(_exec_command_path) as mocked:
            mocked.return_value = self._exec_command_return_value(exit_code=1)
            with self.assertRaises(Exception):
                dc.connector_instance.exec_command('trigger_command_not_found')
            dc.connector_instance.disconnect()
            mocked.assert_called_once()

    @capture_any_output()
    @mock.patch(_connect_path)
    def test_ssh_exec_timeout(self, *args):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connector_instance.connect()
        with mock.patch(_exec_command_path) as mocked:
            mocked.side_effect = socket.timeout()
            with self.assertRaises(socket.timeout):
                dc.connector_instance.exec_command('trigger_timeout')
            dc.connector_instance.disconnect()
            mocked.assert_called_once()

    @capture_any_output()
    @mock.patch(_connect_path)
    def test_ssh_exec_exception(self, *args):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connector_instance.connect()
        with mock.patch(_exec_command_path) as mocked:
            mocked.side_effect = RuntimeError('test')
            with self.assertRaises(RuntimeError):
                dc.connector_instance.exec_command('trigger_exception')
            dc.connector_instance.disconnect()
            mocked.assert_called_once()

    def test_connect_no_addresses(self):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.device.last_ip = None
        dc.device.management_ip = None
        dc.save()
        with self.assertRaises(ValueError):
            dc.connector_instance.connect()

    def test_is_working_change_signal_emitted(self):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        with catch_signal(is_working_changed) as handler:
            dc.is_working = True
            dc.save()
        handler.assert_called_once_with(
            failure_reason='',
            old_failure_reason='',
            instance=dc,
            is_working=True,
            old_is_working=None,
            sender=DeviceConnection,
            signal=is_working_changed,
        )

    def test_operator_group_permissions(self):
        group = Group.objects.get(name='Operator')
        permissions = group.permissions.filter(
            content_type__app_label=f'{self.app_label}'
        )
        self.assertEqual(permissions.count(), 6)

    def test_administrator_group_permissions(self):
        group = Group.objects.get(name='Administrator')
        permissions = group.permissions.filter(
            content_type__app_label=f'{self.app_label}'
        )
        self.assertEqual(permissions.count(), 12)

    def test_device_connection_set_connector(self):
        dc = self._create_device_connection()
        connector = dc.connector_class(
            params=dc.get_params(), addresses=dc.get_addresses()
        )
        connector.IS_MODIFIED = True
        self.assertFalse(hasattr(dc.connector_instance, 'IS_MODIFIED'))
        del dc.connector_instance
        dc.set_connector(connector)
        self.assertTrue(hasattr(dc.connector_instance, 'IS_MODIFIED'))
        self.assertTrue(dc.connector_instance, 'IS_MODIFIED')
        dc.credentials.delete()
        # ensure change not permanent
        org2 = self._create_org(name='org2')
        dev2 = self._create_device(organization=org2)
        self._create_config(device=dev2)
        dc2 = self._create_device_connection(device=dev2)
        self.assertFalse(hasattr(dc2.connector_instance, 'IS_MODIFIED'))

    def test_command_str(self):
        with self.subTest('custom command short'):
            command = Command(type='custom', input={'command': 'echo test'})
            self.assertIn('«echo test» sent on', str(command))
        with self.subTest('custom command long'):
            cmd = {'command': 'echo "longer than thirtytwo characters"'}
            command = Command(type='custom', input=cmd)
            self.assertIn('«echo "longer than thirtytwo char…»', str(command))
        with self.subTest('predefined command'):
            command = Command(type='reboot')
            created = timezone.localtime(command.created).strftime(
                "%d %b %Y at %I:%M %p"
            )
            self.assertIn('«Reboot» sent on', str(command))
            self.assertIn(created, str(command))

    def test_command_arguments(self):
        with self.subTest('Test arguments for a custom command'):
            command = Command(type='custom', input={'command': 'echo test'})
            with self.assertRaises(TypeError):
                command.arguments

        with self.subTest('Test arguments for change password command'):
            command = Command(
                type='change_password',
                input={'password': 'Pass@1234', 'confirm_password': 'Pass@1234'},
            )
            self.assertEqual(list(command.arguments), ['Pass@1234', 'Pass@1234'])

    def test_command_is_custom(self):
        command = Command(type='custom', input={'command': 'echo test'})
        self.assertTrue(command.is_custom)

    def test_command_validation(self):
        dc = self._create_device_connection()
        command = Command(
            device=dc.device, type='custom', input={'command': 'echo test'}
        )

        with self.subTest('auto connection'):
            command.full_clean()
            self.assertEqual(command.connection, dc)
            self.assertEqual(command.input, {'command': 'echo test'})

        with self.subTest('custom type without input raises ValidationError'):
            command.type = 'custom'
            command.input = {'command': '\n'}
            with self.assertRaises(ValidationError) as context_manager:
                command.full_clean()
            e = context_manager.exception
            self.assertIn('input', e.message_dict)
            self.assertEqual(e.message_dict['input'], ["'\\n' does not match '.'"])

        with self.subTest('test extra arg on reboot'):
            command.type = 'reboot'
            command.input = '["test"]'
            with self.assertRaises(ValidationError) as context_manager:
                command.full_clean()
            e = context_manager.exception
            self.assertIn('input', e.message_dict)
            self.assertEqual(
                e.message_dict['input'], ["['test'] is not of type 'null'"]
            )

        with self.subTest('test extra arg on password'):
            command.type = 'change_password'
            command.input = {
                'password': 'Pass@1234',
                'confirm_password': 'Pass@1234',
                'command': 'wrong',
            }
            with self.assertRaises(ValidationError) as context_manager:
                command.full_clean()
            e = context_manager.exception
            self.assertIn('input', e.message_dict)
            self.assertIn(
                'Additional properties are not allowed',
                e.message_dict['input'][0],
            )

        with self.subTest('JSON check on arguments'):
            command.type = 'change_password'
            command.input = 'notjson'
            with self.assertRaises(ValidationError) as context_manager:
                command.full_clean()
            e = context_manager.exception
            self.assertIn('input', e.message_dict)
            self.assertEqual(
                e.message_dict['input'],
                ['Enter valid JSON.', "'notjson' is not of type 'object'"],
            )

        with self.subTest('JSON check on arguments'):
            command.type = 'change_password'
            command.input = '[]'
            with self.assertRaises(ValidationError) as context_manager:
                command.full_clean()
            e = context_manager.exception
            self.assertIn('input', e.message_dict)
            self.assertEqual(e.message_dict['input'], ["[] is not of type 'object'"])

    def test_custom_command(self):
        command = Command(input='test', type='change_password')
        with self.assertRaises(TypeError) as context_manager:
            command.custom_command
        self.assertEqual(
            str(context_manager.exception),
            'custom_commands property is not applicable in '
            'command instance of type "change_password"',
        )

    def test_arguments(self):
        command = Command(
            type='change_password',
            input={'password': 'newpwd', 'confirm_password': 'newpwd'},
        )
        self.assertEqual(list(command.arguments), ['newpwd', 'newpwd'])

        with self.subTest('value error'):
            command = Command(input='["echo test"]', type='custom')
            with self.assertRaises(TypeError) as context_manager:
                command.arguments
            self.assertEqual(
                str(context_manager.exception),
                'arguments property is not applicable in '
                'command instance of type "custom"',
            )

    @mock.patch(_connect_path)
    def test_execute_command_failure_exit_code(self, connect_mocked):
        dc = self._create_device_connection()
        command = Command(
            device=dc.device,
            connection=dc,
            type='custom',
            input={'command': 'cat /tmp/doesntexist'},
        )
        command.full_clean()
        stdout = 'not found'
        stderr = 'error'
        with mock.patch(_exec_command_path) as mocked:
            mocked.return_value = self._exec_command_return_value(
                stdout=stdout, stderr=stderr, exit_code=1
            )
            command.save()
            # must call this explicitly because lack of transactions in this test case
            command.execute()
            connect_mocked.assert_called_once()
            mocked.assert_called_once()
        command.refresh_from_db()
        self.assertEqual(command.status, 'failed')
        info = 'Command "cat /tmp/doesntexist" returned non-zero exit code: 1'
        self.assertEqual(command.output, f'{stdout}\n{stderr}\n{info}\n')

    def test_execute_command_failure_connection_failed(self):
        dc = self._create_device_connection()
        command = Command(
            device=dc.device,
            connection=dc,
            type='custom',
            input={'command': 'echo test'},
        )
        command.full_clean()
        with mock.patch(_connect_path) as mocked_connect:
            mocked_connect.side_effect = Exception('Authentication failed.')
            command.save()
            # must call this explicitly because lack of transactions in this test case
            command.execute()
            mocked_connect.assert_called_once()
        command.refresh_from_db()
        dc.refresh_from_db()
        self.assertEqual(command.status, 'failed')
        self.assertFalse(dc.is_working)
        self.assertEqual(command.output, dc.failure_reason)

        with self.subTest('attempt to repeat execution should fail'):
            with self.assertRaises(RuntimeError) as context_manager:
                command.execute()
            self.assertEqual(
                str(context_manager.exception),
                'This command has already been executed, ' 'please create a new one.',
            )

    @mock.patch(_connect_path)
    def test_execute_reboot(self, connect_mocked):
        dc = self._create_device_connection()
        command = Command(device=dc.device, connection=dc, type='reboot')
        command.full_clean()
        with mock.patch(_exec_command_path) as mocked_exec_command:
            mocked_exec_command.return_value = self._exec_command_return_value(
                stdout='Rebooting.'
            )
            command.save()
            # must call this explicitly because lack of transactions in this test case
            command.execute()
            connect_mocked.assert_called_once()
            mocked_exec_command.assert_called_once()
            mocked_exec_command.assert_called_with(
                'reboot', timeout=app_settings.SSH_COMMAND_TIMEOUT
            )
        command.refresh_from_db()
        self.assertEqual(command.status, 'success')
        self.assertEqual(command.output, 'Rebooting.\n')

        with self.subTest('attempt to repeat execution should fail'):
            with self.assertRaises(RuntimeError) as context_manager:
                command.execute()
            self.assertEqual(
                str(context_manager.exception),
                'This command has already been executed, ' 'please create a new one.',
            )

    @mock.patch(_connect_path)
    def test_execute_change_password(self, connect_mocked):
        dc = self._create_device_connection()
        command = Command(
            device=dc.device,
            connection=dc,
            type='change_password',
            input={'password': 'Newpasswd@123', 'confirm_password': 'Newpasswd@123'},
        )
        command.full_clean()
        with mock.patch(_exec_command_path) as mocked_exec_command:
            mocked_exec_command.return_value = self._exec_command_return_value(
                stdout='Changed password for user root.'
            )
            command.save()
            # must call this explicitly because lack of transactions in this test case
            command.execute()
            connect_mocked.assert_called_once()
            mocked_exec_command.assert_called_once()
            mocked_exec_command.assert_called_with(
                'echo -e "Newpasswd@123\nNewpasswd@123" | passwd root',
                timeout=app_settings.SSH_COMMAND_TIMEOUT,
            )
        command.refresh_from_db()
        self.assertEqual(command.status, 'success')
        self.assertEqual(command.output, 'Changed password for user root.\n')
        self.assertEqual(list(command.arguments), ['********'])

    @mock.patch(_connect_path)
    def test_execute_user_registered_command(self, connect_mocked):
        @mock.patch(_exec_command_path)
        def _command_assertions(destination_address, mocked_exec_command):
            command.full_clean()
            mocked_exec_command.return_value = self._exec_command_return_value(
                stdout='Destination host unreachable'
            )
            command.save()
            # must call this explicitly because lack of transactions in this test case
            command.execute()
            connect_mocked.assert_called()
            mocked_exec_command.assert_called_once()
            mocked_exec_command.assert_called_with(
                f'ping -c 4 {destination_address} -I eth0',
                timeout=app_settings.SSH_COMMAND_TIMEOUT,
            )
            command.refresh_from_db()
            self.assertEqual(command.status, 'success')
            self.assertEqual(command.output, stderr + '\n')

        ping_command_schema = {
            'label': 'Ping',
            'schema': {
                'title': 'Ping',
                'type': 'object',
                'required': ['destination_address'],
                'properties': {
                    'destination_address': {
                        'type': 'string',
                        'title': 'Destination Address',
                        'pattern': '.',
                    },
                    'interface_name': {'type': 'string', 'title': 'Interface Name'},
                },
                'message': 'Destination Address cannot be empty',
                'additionalProperties': False,
            },
        }
        callable_path = (
            'openwisp_controller.connection.tests.utils.' '_ping_command_callable'
        )
        dc = self._create_device_connection()
        stderr = 'Destination host unreachable'

        with self.subTest('Callable is a method'):
            ping_command_schema['callable'] = import_string(callable_path)
            register_command('callable_ping', ping_command_schema)
            command = Command(
                device=dc.device,
                connection=dc,
                type='callable_ping',
                input={'destination_address': 'example.com', 'interface_name': 'eth0'},
            )
            _command_assertions('example.com')

        with self.subTest('Callable is dotted path'):
            ping_command_schema['callable'] = callable_path
            register_command('path_ping', ping_command_schema)
            command = Command(
                device=dc.device,
                connection=dc,
                type='path_ping',
                input={
                    'destination_address': 'subdomain.example.com',
                    'interface_name': 'eth0',
                },
            )
            _command_assertions('subdomain.example.com')

        unregister_command('callable_ping')
        unregister_command('path_ping')

    def test_command_permissions(self):
        ct = ContentType.objects.get_by_natural_key(
            app_label=self.app_label, model='command'
        )
        operator_group = Group.objects.get(name='Operator')
        admin_group = Group.objects.get(name='Administrator')
        operator_permissions = operator_group.permissions.filter(content_type=ct)
        admin_permissions = admin_group.permissions.filter(content_type=ct)

        with self.subTest('operator permissions'):
            self.assertEqual(operator_permissions.count(), 2)
            self.assertTrue(
                operator_permissions.filter(codename='add_command').exists()
            )
            self.assertTrue(
                operator_permissions.filter(codename='view_command').exists()
            )

        with self.subTest('administrator permissions'):
            self.assertEqual(admin_permissions.count(), 4)


class TestModelsTransaction(BaseTestModels, TransactionTestCase):
    def _prepare_conf_object(self, organization=None):
        if not organization:
            organization = self._create_org(name='org1')
        cred = self._create_credentials_with_key(
            organization=organization, port=self.ssh_server.port
        )
        device = self._create_device(organization=organization)
        update_strategy = app_settings.UPDATE_STRATEGIES[0][0]
        conf = self._create_config(device=device, status='applied')
        self._create_device_connection(
            device=device, credentials=cred, update_strategy=update_strategy
        )
        conf.config = {
            'interfaces': [
                {
                    'name': 'eth10',
                    'type': 'ethernet',
                    'addresses': [{'family': 'ipv4', 'proto': 'dhcp'}],
                }
            ]
        }
        conf.full_clean()
        return conf

    @capture_any_output()
    @mock.patch(_connect_path)
    @mock.patch('time.sleep')
    def test_device_config_created(self, mocked_sleep, mocked_connect):
        """
        The update_config task must not be initiated when
        the device has just been created
        """
        test_org = self._get_org()
        self._create_credentials(auto_add=True, organization=test_org)
        self._create_template(default=True, organization=test_org)
        self._prepare_conf_object(organization=test_org)
        mocked_connect.assert_not_called()

    @capture_any_output()
    @mock.patch(_connect_path)
    @mock.patch('time.sleep')
    def test_device_config_update(self, mocked_sleep, mocked_connect):
        def _assert_version_check_command(mocked_exec):
            args, _ = mocked_exec.call_args_list[0]
            self.assertEqual(args[0], 'openwisp_config --version')

        def _assert_applying_conf_test_command(mocked_exec):
            args, _ = mocked_exec_command.call_args_list[1]
            self.assertEqual(
                args[0],
                'test -f /tmp/openwisp/applying_conf',
            )

        conf = self._prepare_conf_object()

        with self.subTest('Unable to get openwisp_config version'):
            with mock.patch(_exec_command_path) as mocked_exec_command:
                mocked_exec_command.return_value = self._exec_command_return_value(
                    exit_code=1
                )
                conf.save()
                self.assertEqual(mocked_exec_command.call_count, 1)
                _assert_version_check_command(mocked_exec_command)
            conf.refresh_from_db()
            self.assertEqual(conf.status, 'modified')

        with self.subTest('openwisp_config >= 0.6.0a'):
            conf.config = '{"dns_servers": []}'
            conf.full_clean()
            with mock.patch(_exec_command_path) as mocked_exec_command:
                mocked_exec_command.return_value = self._exec_command_return_value(
                    stdout='openwisp_config 0.6.0a'
                )
                conf.save()
                self.assertEqual(mocked_exec_command.call_count, 2)
                _assert_version_check_command(mocked_exec_command)
                args, _ = mocked_exec_command.call_args_list[1]
                self.assertIn('OW_CONFIG_PID', args[0])
            conf.refresh_from_db()
            self.assertEqual(conf.status, 'applied')

        with self.subTest('openwisp_config < 0.6.0a: exit_code 0'):
            conf.config = '{"interfaces": []}'
            conf.full_clean()
            with mock.patch(_exec_command_path) as mocked_exec_command:
                mocked_exec_command.return_value = self._exec_command_return_value(
                    stdout='openwisp_config 0.5.0'
                )
                conf.save()
                self.assertEqual(mocked_exec_command.call_count, 2)
                _assert_version_check_command(mocked_exec_command)
                _assert_applying_conf_test_command(mocked_exec_command)
            conf.refresh_from_db()
            self.assertEqual(conf.status, 'applied')

        with self.subTest('openwisp_config < 0.6.0a: exit_code 1'):
            conf.config = '{"radios": []}'
            conf.full_clean()
            with mock.patch(_exec_command_path) as mocked_exec_command:
                stdin, stdout, stderr = self._exec_command_return_value(
                    stdout='openwisp_config 0.5.0'
                )
                # An iterable side effect is required for different exit codes:
                # 1. Checking openwisp_config returns with 0
                # 2. Testing presence of /tmp/openwisp/applying_conf returns with 1
                # 3. Restarting openwisp_config returns with 0 exit code
                stdout.channel.recv_exit_status.side_effect = [0, 1, 1]
                mocked_exec_command.return_value = (stdin, stdout, stderr)
                conf.save()
                self.assertEqual(mocked_exec_command.call_count, 3)
                _assert_version_check_command(mocked_exec_command)
                _assert_applying_conf_test_command(mocked_exec_command)
                args, _ = mocked_exec_command.call_args_list[2]
                self.assertEqual(args[0], '/etc/init.d/openwisp_config restart')
            conf.refresh_from_db()
            # exit code 1 considers the update not successful
            self.assertEqual(conf.status, 'modified')

    @mock.patch.object(update_config, 'delay')
    def test_device_update_config_in_progress(self, mocked_update_config):
        conf = self._prepare_conf_object()

        with mock.patch('celery.app.control.Inspect.active') as mocked_active:
            mocked_active.return_value = {
                'task': [{'name': _TASK_NAME, 'args': [str(conf.device.pk)]}]
            }
            conf.save()
            mocked_active.assert_called_once()
            mocked_update_config.assert_not_called()

    @mock.patch.object(update_config, 'delay')
    def test_device_update_config_not_in_progress(self, mocked_update_config):
        conf = self._prepare_conf_object()

        with mock.patch('celery.app.control.Inspect.active') as mocked_active:
            mocked_active.return_value = {
                'task': [{'name': _TASK_NAME, 'args': ['...']}]
            }
            conf.save()
            mocked_active.assert_called_once()
            mocked_update_config.assert_called_once_with(conf.device.pk)

    @mock.patch(_connect_path)
    def test_schedule_command_called(self, connect_mocked):
        dc = self._create_device_connection()
        command = Command(
            device=dc.device,
            connection=dc,
            type='custom',
            input={'command': 'echo test'},
        )
        command.full_clean()
        with mock.patch(_exec_command_path) as mocked:
            mocked.return_value = self._exec_command_return_value()
            command.save()
            connect_mocked.assert_called_once()
            mocked.assert_called_once()
        command.refresh_from_db()
        self.assertEqual(command.status, 'success')
        self.assertEqual(command.output, 'mocked\n')

    def test_auto_add_to_existing_device_on_edit(self):
        d = self._create_device(organization=self._get_org())
        self._create_config(device=d)
        self.assertEqual(d.deviceconnection_set.count(), 0)
        c = self._create_credentials(auto_add=False, organization=None)
        org2 = Organization.objects.create(name='org2', slug='org2')
        self._create_credentials(name='cred2', auto_add=True, organization=org2)
        d.refresh_from_db()
        self.assertEqual(d.deviceconnection_set.count(), 0)
        c.auto_add = True
        c.full_clean()
        c.save()
        d.refresh_from_db()
        self.assertEqual(d.deviceconnection_set.count(), 1)
        self.assertEqual(d.deviceconnection_set.first().credentials, c)
        # ensure further edits are idempotent
        c.name = 'changed'
        c.full_clean()
        c.save()
        d.refresh_from_db()
        self.assertEqual(d.deviceconnection_set.count(), 1)
        self.assertEqual(d.deviceconnection_set.first().credentials, c)

    def test_auto_add_to_existing_device_on_creation(self):
        d = self._create_device(organization=self._get_org())
        self._create_config(device=d)
        self.assertEqual(d.deviceconnection_set.count(), 0)
        c = self._create_credentials(auto_add=True, organization=None)
        org2 = Organization.objects.create(name='org2', slug='org2')
        self._create_credentials(name='cred2', auto_add=True, organization=org2)
        d.refresh_from_db()
        self.assertEqual(d.deviceconnection_set.count(), 1)
        self.assertEqual(d.deviceconnection_set.first().credentials, c)
        self._create_credentials(name='cred3', auto_add=False, organization=None)
        d.refresh_from_db()
        self.assertEqual(d.deviceconnection_set.count(), 1)
        self.assertEqual(d.deviceconnection_set.first().credentials, c)

    def test_chunk_size(self):
        org = self._get_org()
        self._create_config(device=self._create_device(organization=org))
        self._create_config(
            device=self._create_device(
                organization=org, name='device2', mac_address='22:22:22:22:22:22'
            )
        )
        self._create_config(
            device=self._create_device(
                organization=org, name='device3', mac_address='33:33:33:33:33:33'
            )
        )
        with self.assertNumQueries(28):
            credential = self._create_credentials(auto_add=True, organization=org)
        self.assertEqual(credential.deviceconnection_set.count(), 3)

        with mock.patch.object(Credentials, 'chunk_size', 2):
            with self.assertNumQueries(30):
                credential = self._create_credentials(
                    name='Mocked Credential', auto_add=True, organization=org
                )
