from django.core.exceptions import ValidationError
from django.test import TestCase
from django_loci.tests.base.test_models import BaseTestModels
from swapper import load_model

from .utils import TestGeoMixin

Device = load_model('config', 'Device')
Location = load_model('geo', 'Location')
FloorPlan = load_model('geo', 'FloorPlan')
DeviceLocation = load_model('geo', 'DeviceLocation')


class TestModels(TestGeoMixin, BaseTestModels, TestCase):
    object_model = Device
    location_model = Location
    floorplan_model = FloorPlan
    object_location_model = DeviceLocation

    def test_floorplan_location_validation(self):
        fl = self._create_floorplan()
        fl.location = None
        self.assertFalse(hasattr(fl, 'location'))
        try:
            fl.full_clean()
        except ValidationError as e:
            self.assertIn('location', e.message_dict)
        else:
            self.fail('ValidationError not raised')
