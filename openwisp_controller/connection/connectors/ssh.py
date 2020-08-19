import logging
import socket
from io import BytesIO, StringIO

import paramiko
from django.utils.functional import cached_property
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

    @classmethod
    def custom_validation(cls, params):
        if 'password' not in params and 'key' not in params:
            raise SchemaError('Missing password or key')

    @cached_property
    def params(self):
        params = self._params.copy()
        if 'key' in params:
            key_fileobj = StringIO(params.pop('key'))
            params['pkey'] = paramiko.RSAKey.from_private_key(key_fileobj)
        return params

    def connect(self):
        success = False
        exception = None
        addresses = self.addresses
        if not addresses:
            raise ValueError('No valid IP addresses to initiate connections found')
        for address in addresses:
            try:
                self.shell.connect(
                    address,
                    auth_timeout=app_settings.SSH_AUTH_TIMEOUT,
                    banner_timeout=app_settings.SSH_BANNER_TIMEOUT,
                    timeout=app_settings.SSH_CONNECTION_TIMEOUT,
                    **self.params
                )
            except Exception as e:
                exception = e
            else:
                success = True
                break
        if not success:
            raise exception

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
        print('$:> {0}'.format(command))
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
        output = stdout.read().decode('utf8').strip()
        if output:
            print(output)
        # log standard error
        error = stderr.read().decode('utf8').strip()
        if error:
            print(error)
        # abort the operation if any of the command
        # returned with a non-zero exit status
        if exit_status not in exit_codes and raise_unexpected_exit:
            print('# Previous command failed, aborting...')
            message = error if error else output
            raise CommandFailedException(message)
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
