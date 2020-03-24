from django.contrib.gis.geos import LineString, Point, Polygon
from django.core.exceptions import ValidationError
from django.test import TestCase
from django_loci.tests.base.test_models import BaseTestModels

from ...config.models import Device
from ..models import DeviceLocation, FloorPlan, Location
from . import TestGeoMixin


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

    def test_add_location_with_point_geometry(self):
        self._create_location(geometry=Point(0, 0, srid=4326), name='point')
        obj = self.location_model.objects.get(name='point')
        self.assertEqual(obj.name, 'point')

    def test_add_location_with_line_geometry(self):
        with self.assertRaisesMessage(ValidationError, 'Only point geometry is allowed'):
            self._create_location(geometry=LineString((0, 0), (1, 1), srid=4326), name='line')
        obj = self.location_model.objects.filter(name='line')
        self.assertEqual(obj.count(), 0)

    def tes_add_location_with_polygon_geometry(self):
        with self.assertRaisesMessage(ValidationError, 'Only point geometry is allowed'):
            poly = Polygon((0, 0), (0, 1), (1, 1), (1, 0), (0, 0), srid=4326)
            self._create_location(geometry=poly, name='poly')
        obj = self.location_model.objects.filter(name='poly')
        self.assertEqual(obj.count(), 0)
