from django.test import TestCase

from ..models import FloorPlan, Location, ObjectLocation
from .base.test_models import BaseTestModels
from .testdeviceapp.models import Device


class TestModels(BaseTestModels, TestCase):
    object_model = Device
    location_model = Location
    floorplan_model = FloorPlan
    object_location_model = ObjectLocation
