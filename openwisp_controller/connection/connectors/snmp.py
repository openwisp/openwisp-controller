import logging
from io import StringIO

import paramiko
from django.utils.functional import cached_property
from jsonschema import validate
from jsonschema.exceptions import ValidationError as SchemaError

logger = logging.getLogger(__name__)


class Snmp(object):
    schema = {
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'type': 'object',
        'title': 'Credentials type',
        'oneOf': [
            {
                'title': 'SNMP',
                'required': ['community', 'agent'],
                'additionalProperties': False,
                'properties': {
                    'community': {'type': 'string', 'default': 'public'},
                    'agent': {'type': 'string'},
                    'port': {
                        'type': 'integer',
                        'default': 161,
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

    @classmethod
    def validate(cls, params):
        validate(params, cls.schema)
        cls.custom_validation(params)

    @classmethod
    def custom_validation(cls, params):
        if 'community' not in params or 'agent' not in params:
            raise SchemaError('Missing password or key')

    @cached_property
    def params(self):
        params = self._params.copy()
        if 'key' in params:
            key_fileobj = StringIO(params.pop('key'))
            params['pkey'] = paramiko.RSAKey.from_private_key(key_fileobj)
        return params
