from django.test import TestCase
from django_loci.tests.base.test_models import BaseTestModels

from . import TestGeoMixin
from ...config.models import Device
from ..models import DeviceLocation, FloorPlan, Location


class TestModels(TestGeoMixin, BaseTestModels, TestCase):
    object_model = Device
    location_model = Location
    floorplan_model = FloorPlan
    object_location_model = DeviceLocation
