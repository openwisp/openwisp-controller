import logging

from jsonschema import validate

logger = logging.getLogger(__name__)


class Snmp(object):
    schema = {
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'type': 'object',
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
    }

    has_update_strategy = False

    def __init__(self, params, addresses):
        self.params = params
        self.addresses = addresses

    @classmethod
    def validate(cls, params):
        validate(params, cls.schema)
