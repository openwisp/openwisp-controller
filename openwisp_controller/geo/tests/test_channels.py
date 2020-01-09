from channels.test import ChannelTestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django_loci.tests.base.test_channels import BaseTestChannels

from . import TestGeoMixin
from ...config.models import Device
from ..models import DeviceLocation, Location


class TestChannels(TestGeoMixin, BaseTestChannels, ChannelTestCase):
    object_model = Device
    location_model = Location
    object_location_model = DeviceLocation
    user_model = get_user_model()

    def test_consumer_staff_but_no_change_permission(self):
        user = self.user_model.objects.create_user(username='user',
                                                   password='password',
                                                   email='test@test.org',
                                                   is_staff=True)
        location = self._create_location(is_mobile=True)
        ol = self._create_object_location(location=location)
        pk = ol.location.pk
        try:
            self._test_consume(pk=pk, user=user)
        except AssertionError as e:
            self.assertIn('Connection rejected', str(e))
        else:
            self.fail('AssertionError not raised')
        # add permission to change location and repeat
        perm = Permission.objects.filter(name='Can change location').first()
        user.user_permissions.add(perm)
        try:
            self._test_consume(pk=pk, user=user)
        except AssertionError as e:
            self.assertIn('Connection rejected', str(e))
        else:
            self.fail('AssertionError not raised')
        # add user to organization
        location.organization.add_user(user)
        location.organization.save()
        self._test_consume(pk=pk, user=user)
