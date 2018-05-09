import logging
import sys

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

    def update_config(self):
        raise NotImplementedError()

    def upload(self, fl, remote_path):
        scp = SCPClient(self.shell.get_transport())
        scp.putfo(fl, remote_path)
        scp.close()
