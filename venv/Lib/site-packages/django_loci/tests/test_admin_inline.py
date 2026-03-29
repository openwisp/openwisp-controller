from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import FloorPlan, Location, ObjectLocation
from .base.test_admin_inline import BaseTestAdminInline
from .testdeviceapp.models import Device


class TestAdminInline(BaseTestAdminInline, TestCase):
    object_model = Device
    location_model = Location
    floorplan_model = FloorPlan
    object_location_model = ObjectLocation
    user_model = get_user_model()
