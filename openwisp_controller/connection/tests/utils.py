import os

from mockssh import Server
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin

from ...config.tests.utils import CreateConfigTemplateMixin
from .. import settings as app_settings

Credentials = load_model('connection', 'Credentials')
DeviceConnection = load_model('connection', 'DeviceConnection')
Command = load_model('connection', 'Command')


class SshServer(Server):
    def _run(self, *args, **kwargs):
        """
        Hides 'Bad file descriptor' system issue which
        does not affect the effectivness of the tests
        """
        try:
            return super()._run(*args, **kwargs)
        except OSError as e:
            if str(e) == '[Errno 9] Bad file descriptor':
                pass
            else:
                raise e


class CreateConnectionsMixin(CreateConfigTemplateMixin, TestOrganizationMixin):

    _TEST_RSA_PRIVATE_KEY_PATH = os.path.join(os.path.dirname(__file__), 'test-key.rsa')
    _TEST_RSA_PRIVATE_KEY_VALUE = None
    _TEST_ED_PRIVATE_KEY_PATH = os.path.join(
        os.path.dirname(__file__), 'test-key.ed25519'
    )
    _TEST_ED_PRIVATE_KEY_VALUE = None

    class ssh_server:
        host = '127.0.0.1'
        port = 5555

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(cls._TEST_RSA_PRIVATE_KEY_PATH, 'r') as f:
            cls._TEST_RSA_PRIVATE_KEY_VALUE = f.read()
        with open(cls._TEST_ED_PRIVATE_KEY_PATH, 'r') as f:
            cls._TEST_ED_PRIVATE_KEY_VALUE = f.read()

    def _create_device(self, *args, **kwargs):
        if 'last_ip' not in kwargs and 'management_ip' not in kwargs:
            kwargs.update(
                {'last_ip': self.ssh_server.host, 'management_ip': self.ssh_server.host}
            )
        return super()._create_device(*args, **kwargs)

    def _get_credentials(self, **kwargs):
        opts = {'name': 'Test credentials'}
        opts.update(**kwargs)
        try:
            return Credentials.objects.get(**opts)
        except Credentials.DoesNotExist:
            return self._create_credentials(**opts)

    def _create_credentials(self, **kwargs):
        opts = dict(
            name='Test credentials',
            connector=app_settings.CONNECTORS[0][0],
            params={'username': 'root', 'password': 'password', 'port': 22},
        )
        opts.update(kwargs)
        if 'organization' not in opts:
            opts['organization'] = self._get_org()
        c = Credentials(**opts)
        c.full_clean()
        c.save()
        return c

    def _create_credentials_with_key(self, username='root', port=22, **kwargs):
        opts = dict(
            name='Test SSH Key',
            params={
                'username': username,
                'key': self._TEST_RSA_PRIVATE_KEY_VALUE,
                'port': port,
            },
        )
        opts.update(kwargs)
        return self._create_credentials(**opts)

    def _create_credentials_with_ed_key(self, username='root', port=22, **kwargs):
        opts = dict(
            name='Test SSH Key',
            params={
                'username': username,
                'key': self._TEST_ED_PRIVATE_KEY_VALUE,
                'port': port,
            },
        )
        opts.update(kwargs)
        return self._create_credentials(**opts)

    def _create_device_connection(self, **kwargs):
        opts = dict(enabled=True, params={})
        opts.update(kwargs)
        if 'credentials' not in opts:
            cred_opts = {}
            if 'device' in opts:
                cred_opts = {'organization': opts['device'].organization}
            opts['credentials'] = self._create_credentials(**cred_opts)
        org = opts['credentials'].organization
        if 'device' not in opts:
            opts['device'] = self._create_device(organization=org)
            self._create_config(device=opts['device'])
        dc = DeviceConnection(**opts)
        dc.full_clean()
        dc.save()
        return dc


class CreateCommandMixin(CreateConnectionsMixin):
    def _create_command(self, device_conn=None, device_conn_opts={}, **kwargs):
        if device_conn is None:
            device_conn = self._create_device_connection(**device_conn_opts)
        opts = {
            'device': device_conn.device,
            'connection': device_conn,
            'type': 'custom',
            'input': {'command': 'echo test'},
        }
        return Command.objects.create(**opts)


def _ping_command_callable(destination_address, interface_name=None):
    command = f'ping -c 4 {destination_address}'
    if interface_name:
        command += f' -I {interface_name}'
    return command
