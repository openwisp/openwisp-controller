import logging
from io import StringIO

<<<<<<< HEAD
import paramiko
from django.utils.functional import cached_property
=======
>>>>>>> e90597d ([misc] Requested changes)
from jsonschema import validate

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
        self.params = params
        self.addresses = addresses

    @classmethod
    def validate(cls, params):
        validate(params, cls.schema)
