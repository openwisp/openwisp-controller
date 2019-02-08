from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django_loci.tests.base.test_admin_inline import BaseTestAdminInline

from . import TestGeoMixin
from ...config.models import Device
from ...config.tests.test_admin import TestAdmin as TestConfigAdmin
from ..models import DeviceLocation, FloorPlan, Location

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
    object_model = Device
    location_model = Location
    floorplan_model = FloorPlan
    object_location_model = DeviceLocation
    user_model = get_user_model()
    app_label = 'geo'
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

    def test_add_new_location_without_type(self):
        self._login_as_admin()
        p = self._get_prefix()
        params = self.params
        params.update({
            '{0}-0-type'.format(p): '',
            '{0}-0-location_selection'.format(p): 'new',
            '{0}-0-location'.format(p): '',
            '{0}-0-floorplan_selection'.format(p): '',
            '{0}-0-floorplan'.format(p): '',
            '{0}-0-floor'.format(p): '',
            '{0}-0-image'.format(p): '',
            '{0}-0-indoor'.format(p): '',
            '{0}-0-id'.format(p): '',
            '{0}-0-geometry'.format(p): '',
            '{0}-0-content_object'.format(p): '',
            '{0}-0-address'.format(p): ''
        })
        try:
            self.client.post(reverse(self.add_url), params, follow=True)
        except KeyError:
            self.assertFalse(True)
