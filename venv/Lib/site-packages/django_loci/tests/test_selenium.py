from channels.testing import ChannelsLiveServerTestCase
from django.contrib.auth import get_user_model
from django.test import tag

from ..models import Location, ObjectLocation
from .base.test_selenium import BaseTestDeviceAdminSelenium
from .testdeviceapp.models import Device


@tag("selenium_tests")
class TestDeviceAdminSelenium(BaseTestDeviceAdminSelenium, ChannelsLiveServerTestCase):
    user_model = get_user_model()
    object_model = Device
    location_model = Location
    object_location_model = ObjectLocation
