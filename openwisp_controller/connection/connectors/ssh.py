import ipaddress
import logging

import paramiko
from django.core.exceptions import ObjectDoesNotExist
from django.utils.functional import cached_property
from jsonschema import validate
from jsonschema.exceptions import ValidationError as SchemaError
from scp import SCPClient

from ..utils import get_interfaces

try:
    from io import StringIO
except ImportError:
    from StringIO import StringIO


logger = logging.getLogger(__name__)


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

    def __init__(self, device_connection):
        self.connection = device_connection
        self.device = device_connection.device
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
    def _addresses(self):
        deviceip_set = list(self.device.deviceip_set.all()
                                       .only('address')
                                       .order_by('priority'))
        address_list = []
        for deviceip in deviceip_set:
            address = deviceip.address
            ip = ipaddress.ip_address(address)
            if not ip.is_link_local:
                address_list.append(address)
            else:
                for interface in get_interfaces():
                    address_list.append('{0}%{1}'.format(address, interface))
        try:
            address_list.append(self.device.config.last_ip)
        except ObjectDoesNotExist:
            pass
        return address_list

    @cached_property
    def _params(self):
        params = self.connection.get_params()
        if 'key' in params:
            key_fileobj = StringIO(params.pop('key'))
            params['pkey'] = paramiko.RSAKey.from_private_key(key_fileobj)
        return params

    def connect(self):
        success = False
        exception = None
        for address in self._addresses:
            try:
                self.shell.connect(address, **self._params)
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
