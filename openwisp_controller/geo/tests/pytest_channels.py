import importlib

import pytest
from channels.routing import ProtocolTypeRouter
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.models import Permission
from django.http.request import HttpRequest
from openwisp_controller.geo.channels.consumers import LocationBroadcast

from . import TestGeoMixin
from ...config.models import Device
from ..models import DeviceLocation, Location


class TestChannels(TestGeoMixin):
    object_model = Device
    location_model = Location
    object_location_model = DeviceLocation
    user_model = get_user_model()

    def _force_login(self, user, backend=None):
        engine = importlib.import_module(settings.SESSION_ENGINE)
        request = HttpRequest()
        request.session = engine.SessionStore()
        login(request, user, backend)
        request.session.save()
        return request.session

    def _get_request_dict(self, pk=None, user=None):
        if not pk:
            location = self._create_location(is_mobile=True)
            self._create_object_location(location=location)
            pk = location.pk
        path = '/ws/loci/location/{0}/'.format(pk)
        session = None
        if user:
            session = self._force_login(user)
        return {'pk': pk, 'path': path, 'session': session}

    def _get_communicator(self, request_vars, user=None):
        communicator = WebsocketCommunicator(LocationBroadcast,
                                             request_vars['path'])
        if user:
            communicator.scope.update({
                "user": user,
                "session": request_vars['session'],
                "url_route": {
                    "kwargs": {
                        "pk": request_vars['pk']
                    }
                }
            })
        return communicator

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_consumer_staff_but_no_change_permission(self):
        user = self.user_model.objects.create_user(username='user',
                                                   password='password',
                                                   email='test@test.org',
                                                   is_staff=True)
        location = self._create_location(is_mobile=True)
        self._create_object_location(location=location)
        pk = location.pk
        request_vars = self._get_request_dict(user=user, pk=pk)
        communicator = self._get_communicator(request_vars, user)
        connected, _ = await communicator.connect()
        assert not connected
        await communicator.disconnect()
        # add permission to change location and repeat
        perm = Permission.objects.filter(name='Can change location').first()
        user.user_permissions.add(perm)
        user = self.user_model.objects.get(pk=user.pk)
        request_vars = self._get_request_dict(user=user, pk=pk)
        communicator = self._get_communicator(request_vars, user)
        connected, _ = await communicator.connect()
        assert not connected
        await communicator.disconnect()
        # add user to organization
        location.organization.add_user(user)
        location.organization.save()
        user = self.user_model.objects.get(pk=user.pk)
        request_vars = self._get_request_dict(user=user, pk=pk)
        communicator = self._get_communicator(request_vars, user)
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    def test_routing(self):
        from openwisp_controller.geo.channels.routing import channel_routing
        assert isinstance(channel_routing, ProtocolTypeRouter)
