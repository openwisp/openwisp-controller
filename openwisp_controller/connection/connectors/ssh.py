import logging
import socket
from io import BytesIO, StringIO

import paramiko
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from jsonschema import validate
from jsonschema.exceptions import ValidationError as SchemaError
from scp import SCPClient

from .. import settings as app_settings
from .exceptions import CommandFailedException

logger = logging.getLogger(__name__)


class Ssh(object):
    schema = {
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'type': 'object',
        'title': 'Credentials type',
        'oneOf': [
            {
                'title': 'SSH (password)',
                'required': ['username', 'password'],
                'additionalProperties': False,
                'properties': {
                    'username': {'type': 'string', 'minLength': 2},
                    'password': {'type': 'string', 'minLength': 4},
                    'port': {
                        'type': 'integer',
                        'default': 22,
                        'minimum': 1,
                        'maximum': 65535,
                    },
                },
            },
            {
                'title': 'SSH (private key)',
                'required': ['username', 'key'],
                'additionalProperties': False,
                'properties': {
                    'username': {'type': 'string'},
                    'key': {'type': 'string', 'format': 'textarea', 'minLength': 64},
                    'port': {
                        'type': 'number',
                        'default': 22,
                        'minimum': 1,
                        'maximum': 65535,
                    },
                },
            },
        ],
    }

    def __init__(self, params, addresses):
        self._params = params
        self.addresses = addresses
        self.shell = paramiko.SSHClient()
        self.shell.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    @classmethod
    def validate(cls, params):
        validate(params, cls.schema)
        cls.custom_validation(params)
        # trigger SSH key algorithm check
        cls(params, ['127.0.0.1']).params

    @classmethod
    def custom_validation(cls, params):
        if 'password' not in params and 'key' not in params:
            raise SchemaError('Missing password or key')

    @cached_property
    def params(self):
        params = self._params.copy()
        if 'key' in params:
            params['pkey'] = self._get_ssh_key(params.pop('key'))
        return params

    def _get_ssh_key(self, key):
        key_fileobj = StringIO(key)
        key_algorithms = [
            paramiko.RSAKey,
            paramiko.Ed25519Key,
        ]
        for key_algo in key_algorithms:
            try:
                return getattr(key_algo, 'from_private_key')(key_fileobj)
            except (paramiko.ssh_exception.SSHException, ValueError):
                key_fileobj.seek(0)
                continue
        else:
            raise SchemaError(
                _(
                    'Unrecognized or unsupported SSH key algorithm, '
                    'only RSA and ED25519 are currently supported.'
                )
            )

    def connect(self):
        success = False
        exception = None
        addresses = self.addresses
        if not addresses:
            raise ValueError('No valid IP addresses to initiate connections found')
        for address in addresses:
            try:
                self._connect(address)
            except Exception as e:
                exception = e
            else:
                success = True
                break
        if not success:
            self.disconnect()
            raise exception

    def _connect(self, address):
        """
        Tries to instantiate the SSH connection,
        if the connection fails, it tries again
        by disabling the new deafult HostKeyAlgorithms
        used by newer versions of Paramiko
        """
        params = self.params
        for attempt in [1, 2]:
            try:
                self.shell.connect(
                    address,
                    auth_timeout=app_settings.SSH_AUTH_TIMEOUT,
                    banner_timeout=app_settings.SSH_BANNER_TIMEOUT,
                    timeout=app_settings.SSH_CONNECTION_TIMEOUT,
                    **params
                )
            except paramiko.ssh_exception.AuthenticationException as e:
                # the authentication failure may be caused by the issue
                # described at https://github.com/paramiko/paramiko/issues/1961
                # let's retry by disabling the new default HostKeyAlgorithms,
                # which can work on older systems.
                if e.args == ('Authentication failed.',) and attempt == 1:
                    params['disabled_algorithms'] = {
                        'pubkeys': ['rsa-sha2-512', 'rsa-sha2-256']
                    }
                    continue
                raise e
            else:
                break

    def disconnect(self):
        self.shell.close()

    def exec_command(
        self,
        command,
        timeout=app_settings.SSH_COMMAND_TIMEOUT,
        exit_codes=[0],
        raise_unexpected_exit=True,
    ):
        """
        Executes a command and performs the following operations
        - logs executed command
        - logs standard output
        - logs standard error
        - aborts on exceptions
        - raises socket.timeout exceptions
        """
        logger.info('Executing command: {0}'.format(command))
        # execute commmand
        try:
            stdin, stdout, stderr = self.shell.exec_command(command, timeout=timeout)
        # re-raise socket.timeout to avoid being catched
        # by the subsequent `except Exception as e` block
        except socket.timeout:
            raise socket.timeout()
        # any other exception will abort the operation
        except Exception as e:
            logger.exception(e)
            raise e
        # store command exit status
        exit_status = stdout.channel.recv_exit_status()
        # log standard output
        # try to decode to UTF-8, ignoring unconvertible characters
        # https://docs.python.org/3/howto/unicode.html#the-string-type
        output = stdout.read().decode('utf-8', 'ignore')
        if output:
            logger.info(output)
        # log standard error
        error = stderr.read().decode('utf-8', 'ignore')
        if error:
            if not output.endswith('\n'):
                output += '\n'
            output += error
        # abort the operation if any of the command
        # returned with a non-zero exit status
        if exit_status not in exit_codes and raise_unexpected_exit:
            log_message = 'Unexpected exit code: {0}'.format(exit_status)
            logger.info(log_message)
            message = error if error else output
            # if message is empty, use log_message
            raise CommandFailedException(message or log_message)
        return output, exit_status

    def update_config(self):  # pragma: no cover
        raise NotImplementedError()

    def upload(self, fl, remote_path):
        scp = SCPClient(self.shell.get_transport())
        if not hasattr(fl, 'getvalue'):
            fl_memory = BytesIO(fl.read())
            fl.seek(0)
            fl = fl_memory
        scp.putfo(fl, remote_path)
        scp.close()
