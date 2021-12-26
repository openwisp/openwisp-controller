from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django_loci.tests.base.test_admin_inline import BaseTestAdminInline
from swapper import load_model

from ...config.tests.test_admin import TestAdmin as TestConfigAdmin
from .utils import TestGeoMixin

Device = load_model('config', 'Device')
Location = load_model('geo', 'Location')
FloorPlan = load_model('geo', 'FloorPlan')
DeviceLocation = load_model('geo', 'DeviceLocation')

# ConfigInline management fields
_device_params = TestConfigAdmin._device_params.copy()
_device_params['config-TOTAL_FORMS'] = 0
_delete_keys = []
for key in _device_params.keys():
    if 'config-0-' in key:
        _delete_keys.append(key)
for key in _delete_keys:
    del _device_params[key]


class TestAdminInline(TestGeoMixin, BaseTestAdminInline, TestCase):
    app_label = 'geo'
    object_model = Device
    location_model = Location
    floorplan_model = FloorPlan
    object_location_model = DeviceLocation
    user_model = get_user_model()

    inline_field_prefix = 'devicelocation'

    def setUp(self):
        self.organization = self._create_organization()

    @classmethod
    def _get_prefix(cls):
        return cls.inline_field_prefix

    @property
    def params(self):
        params = self.__class__._get_params()
        params.update(_device_params)
        params['organization'] = self.organization.pk
        return params

    @mock.patch('openwisp_controller.config.settings.HARDWARE_ID_AS_NAME', False)
    def test_add_mobile(self):
        self._login_as_admin()
        prefix = self._get_prefix()
        params = self.params
        params.update(
            {
                'name': 'test-add-mobile',
                '{0}-0-type'.format(prefix): 'outdoor',
                '{0}-0-is_mobile'.format(prefix): True,
                '{0}-0-location_selection'.format(prefix): 'new',
                '{0}-0-name'.format(prefix): '',
                '{0}-0-address'.format(prefix): '',
                '{0}-0-geometry'.format(prefix): '',
            }
        )
        self.assertEqual(self.location_model.objects.count(), 0)
        res = self.client.post(reverse(self.add_url), params, follow=True)
        self.assertNotContains(res, 'errors')
        self.assertEqual(self.location_model.objects.filter(is_mobile=True).count(), 1)
        self.assertEqual(self.object_location_model.objects.count(), 1)
        loc = self.location_model.objects.first()
        self.assertEqual(
            loc.objectlocation_set.first().content_object.name, params['name']
        )
        self.assertEqual(loc.name, params['name'])


del TestConfigAdmin
