from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin

from .. import settings as app_settings
from .utils import CreateDeviceGroupMixin

DeviceGroup = load_model('config', 'DeviceGroup')


class TestDeviceGroup(TestOrganizationMixin, CreateDeviceGroupMixin, TestCase):
    def test_devicegroup(self):
        self._create_devicegroup(meta_data={'captive_portal_url': 'https//example.com'})
        self.assertEqual(DeviceGroup.objects.count(), 1)

    def test_devicegroup_schema_validation(self):
        devicegroup_schema = {
            'required': ['captive_portal_url'],
            'properties': {
                'captive_portal_url': {
                    'type': 'string',
                    'title': 'Captive Portal URL',
                },
            },
            'additionalProperties': True,
        }

        with patch.object(app_settings, 'DEVICEGROUP_SCHEMA', devicegroup_schema):
            with self.subTest('Test for failing validation'):
                self.assertRaises(ValidationError, self._create_devicegroup)

            with self.subTest('Test for passing validation'):
                self._create_devicegroup(
                    meta_data={'captive_portal_url': 'https://example.com'}
                )
