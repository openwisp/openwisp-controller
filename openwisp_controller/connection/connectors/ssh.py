import logging
import socket
import sys
from io import BytesIO

import paramiko
from django.utils.functional import cached_property
from jsonschema import validate
from jsonschema.exceptions import ValidationError as SchemaError
from scp import SCPClient

if sys.version_info.major > 2:  # pragma: nocover
    from io import StringIO
else:  # pragma: nocover
    from StringIO import StringIO


logger = logging.getLogger(__name__)
SSH_CONNECTION_TIMEOUT = 5
SSH_AUTH_TIMEOUT = 2
SSH_COMMAND_TIMEOUT = 5


class Ssh(object):
    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "type": "object",
        "additionalProperties": False,
        "required": ["username"],
        "properties": {
            "username": {"type": "string"},
            "password": {"type": "string"},
            "key": {"type": "string"},
            "port": {"type": "integer"},
        }
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
        for address in self.addresses:
            try:
                self.shell.connect(address,
                                   timeout=SSH_CONNECTION_TIMEOUT,
                                   auth_timeout=SSH_AUTH_TIMEOUT,
                                   **self.params)
            except Exception as e:
                exception = e
            else:
                success = True
                break
        if not success:
            raise exception

    def disconnect(self):
        self.shell.close()

    def exec_command(self, command, timeout=SSH_COMMAND_TIMEOUT,
                     exit_codes=[0], raise_unexpected_exit=True):
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
            stdin, stdout, stderr = self.shell.exec_command(command)
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
            print('# Previus command failed, aborting upgrade...')
            message = error if error else output
            raise Exception(message)
        return output, exit_status

    def update_config(self):
        raise NotImplementedError()

    def upload(self, fl, remote_path):
        scp = SCPClient(self.shell.get_transport())
        if not hasattr(fl, 'getvalue'):
            fl_memory = BytesIO(fl.read())
            fl.seek(0)
            fl = fl_memory
        scp.putfo(fl, remote_path)
        scp.close()
