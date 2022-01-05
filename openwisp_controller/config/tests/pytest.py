import pytest
from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import Permission
from django.urls import re_path
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin

from ..base.channels_consumer import BaseDeviceConsumer
from .utils import CreateDeviceMixin

Device = load_model('config', 'Device')


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestDeviceConsumer(CreateDeviceMixin, TestOrganizationMixin):
    model = Device
    application = ProtocolTypeRouter(
        {
            'websocket': AllowedHostsOriginValidator(
                AuthMiddlewareStack(
                    URLRouter(
                        [
                            re_path(
                                r'^ws/controller/device/(?P<pk>[^/]+)/$',
                                BaseDeviceConsumer.as_asgi(),
                            )
                        ]
                    )
                )
            )
        }
    )

    async def _get_communicator(self, admin_client, device_id):
        session_id = admin_client.cookies['sessionid'].value
        communicator = WebsocketCommunicator(
            self.application,
            path=f'ws/controller/device/{device_id}/',
            headers=[
                (
                    b'cookie',
                    f'sessionid={session_id}'.encode('ascii'),
                )
            ],
        )
        connected, subprotocol = await communicator.connect()
        assert connected is True
        return communicator

    @database_sync_to_async
    def _add_model_permissions(self, user, add=True, change=True, delete=True):
        permissions = []
        if add:
            permissions.append(f'add_{self.model._meta.model_name}')
        if change:
            permissions.append(f'change_{self.model._meta.model_name}')
        if delete:
            permissions.append(f'delete_{self.model._meta.model_name}')
        user.user_permissions.set(Permission.objects.filter(codename__in=permissions))

    async def test_unauthenticated_user(self, client):
        client.cookies['sessionid'] = 'random'
        device = await database_sync_to_async(self._create_device)()
        with pytest.raises(AssertionError):
            await self._get_communicator(client, device.id)

    async def test_authenticated_user(self, admin_user, admin_client):
        device = await database_sync_to_async(self._create_device)()
        communicator = await self._get_communicator(admin_client, device.id)
        communicator.disconnect()

    async def test_user_authorization(self, client, django_user_model):
        device = await database_sync_to_async(self._create_device)()
        staff_user = await database_sync_to_async(self._create_operator)()
        await database_sync_to_async(client.force_login)(staff_user)

        # Test unauthorized user
        with pytest.raises(AssertionError):
            communicator = await self._get_communicator(client, device.pk)
            await communicator.disconnect()

        # Test with user having all permissions
        await self._add_model_permissions(staff_user)
        await database_sync_to_async(client.force_login)(staff_user)
        communicator = await self._get_communicator(client, device.pk)
        await communicator.disconnect()

    async def test_silent_disconnection(self, admin_user, admin_client):
        device = await database_sync_to_async(self._create_device)()
        session_id = admin_client.cookies['sessionid'].value
        communicator = WebsocketCommunicator(
            self.application,
            path=f'ws/controller/device/{device.pk}/',
            headers=[
                (
                    b'cookie',
                    f'sessionid={session_id}'.encode('ascii'),
                )
            ],
        )
        await communicator.disconnect()
