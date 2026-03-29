from django.contrib.auth import get_user_model

from ..models import Location, ObjectLocation
from .base.test_channels import BaseTestChannels
from .testdeviceapp.models import Device


class TestChannels(BaseTestChannels):
    object_model = Device
    location_model = Location
    object_location_model = ObjectLocation
    user_model = get_user_model()
