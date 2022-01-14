import importlib
import os
from unittest import skipIf

import pytest
from channels.db import database_sync_to_async
from channels.routing import ProtocolTypeRouter
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.models import Permission
from django.http.request import HttpRequest
from django.utils.module_loading import import_string
from swapper import load_model

from .utils import TestGeoMixin

Device = load_model('config', 'Device')
Location = load_model('geo', 'Location')
DeviceLocation = load_model('geo', 'DeviceLocation')
User = get_user_model()
OrganizationUser = load_model('openwisp_users', 'OrganizationUser')


@skipIf(os.environ.get('SAMPLE_APP', False), 'Running tests on SAMPLE_APP')
class TestChannels(TestGeoMixin):
    application = import_string(getattr(settings, 'ASGI_APPLICATION'))
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

    async def _get_request_dict(self, pk=None, user=None):
        if not pk:
            location = await database_sync_to_async(self._create_location)(
                is_mobile=True
            )
            await database_sync_to_async(self._create_object_location)(
                location=location
            )
            pk = location.pk
        path = '/ws/loci/location/{0}/'.format(pk)
        session = None
        if user:
            session = await database_sync_to_async(self._force_login)(user)
        return {'pk': pk, 'path': path, 'session': session}

    def _get_communicator(self, request_vars, user=None):
        communicator = WebsocketCommunicator(self.application, request_vars['path'])
        if user:
            communicator.scope.update(
                {
                    'user': user,
                    'session': request_vars['session'],
                    'url_route': {'kwargs': {'pk': request_vars['pk']}},
                }
            )
        return communicator

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_consumer_staff_but_no_change_permission(self):
        user = await database_sync_to_async(User.objects.create_user)(
            username='user', password='password', email='test@test.org', is_staff=True
        )
        location = await database_sync_to_async(self._create_location)(is_mobile=True)
        await database_sync_to_async(self._create_object_location)(location=location)
        pk = location.pk
        request_vars = await self._get_request_dict(user=user, pk=pk)
        communicator = self._get_communicator(request_vars, user)
        connected, _ = await communicator.connect()
        assert not connected
        await communicator.disconnect()
        # add permission to change location and repeat
        perm = await database_sync_to_async(
            (
                await database_sync_to_async(Permission.objects.filter)(
                    name='Can change location'
                )
            ).first
        )()
        await database_sync_to_async(user.user_permissions.add)(perm)
        user = await database_sync_to_async(User.objects.get)(pk=user.pk)
        request_vars = await self._get_request_dict(user=user, pk=pk)
        communicator = self._get_communicator(request_vars, user)
        connected, _ = await communicator.connect()
        assert not connected
        await communicator.disconnect()
        # add user to organization
        await database_sync_to_async(OrganizationUser.objects.create)(
            organization=location.organization, user=user, is_admin=True
        )
        await database_sync_to_async(location.organization.save)()
        user = await database_sync_to_async(User.objects.get)(pk=user.pk)
        request_vars = await self._get_request_dict(user=user, pk=pk)
        communicator = self._get_communicator(request_vars, user)
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    def test_asgi_application_router(self):
        assert isinstance(self.application, ProtocolTypeRouter)
