from unittest import mock

from django.test import TransactionTestCase

from .. import settings as app_settings
from .utils import CreateConnectionsMixin


class TestTransactionBlocks(CreateConnectionsMixin, TransactionTestCase):
    _connect_path = 'paramiko.SSHClient.connect'
    _exec_command_path = 'paramiko.SSHClient.exec_command'

    def _exec_command_return_value(
        self, stdin='', stdout='mocked', stderr='', exit_code=0
    ):
        stdin_ = mock.Mock()
        stdout_ = mock.Mock()
        stderr_ = mock.Mock()
        stdin_.read().decode('utf8').strip.return_value = stdin
        stdout_.read().decode('utf8').strip.return_value = stdout
        stdout_.channel.recv_exit_status.return_value = exit_code
        stderr_.read().decode('utf8').strip.return_value = stderr
        return (stdin_, stdout_, stderr_)

    @mock.patch(_connect_path)
    def test_device_config_update(self, mocked_connect):
        org1 = self._create_org(name='org1')
        cred = self._create_credentials_with_key(
            organization=org1, port=self.ssh_server.port
        )
        device = self._create_device(organization=org1)
        update_strategy = app_settings.UPDATE_STRATEGIES[0][0]
        c = self._create_config(device=device, status='applied')
        self._create_device_connection(
            device=device, credentials=cred, update_strategy=update_strategy
        )
        c.config = {
            'interfaces': [
                {
                    'name': 'eth10',
                    'type': 'ethernet',
                    'addresses': [{'family': 'ipv4', 'proto': 'dhcp'}],
                }
            ]
        }
        c.full_clean()

        with mock.patch(self._exec_command_path) as mocked:
            mocked.return_value = self._exec_command_return_value()
            c.save()
            c.refresh_from_db()
            mocked.assert_called_once()
        c.refresh_from_db()
        self.assertEqual(c.status, 'applied')
