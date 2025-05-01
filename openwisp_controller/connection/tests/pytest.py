from unittest import mock

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string
from swapper import load_model

from openwisp_controller.connection.tests.utils import CreateCommandMixin

from .test_models import BaseTestModels

Command = load_model('connection', 'Command')


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCommandsConsumer(BaseTestModels, CreateCommandMixin):
    application = import_string(getattr(settings, 'ASGI_APPLICATION'))

    async def _get_communicator(self, admin_client, device_id):
        session_id = admin_client.cookies['sessionid'].value
        communicator = WebsocketCommunicator(
            self.application,
            path=f'ws/controller/device/{device_id}/command',
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

    async def _create_command(self, device_conn):
        command = Command(
            device_id=device_conn.device_id,
            connection=device_conn,
            type='custom',
            input={'command': 'echo test'},
        )
        await database_sync_to_async(command.full_clean)()
        with mock.patch('paramiko.SSHClient.exec_command') as mocked_exec_command:
            mocked_exec_command.return_value = self._exec_command_return_value(
                stdout='test'
            )
        await database_sync_to_async(command.save)()
        await database_sync_to_async(command.refresh_from_db)()
        return command

    def _get_expected_response(self, command):
        return {
            'model': 'Command',
            'data': {
                'id': str(command.id),
                'created': timezone.localtime(command.created).isoformat(),
                'modified': timezone.localtime(command.modified).isoformat(),
                'status': command.status,
                'type': 'Custom commands',
                'input': command.input_data,
                'output': command.output,
                'device': str(command.device_id),
                'connection': str(command.connection_id),
            },
        }

    @mock.patch('paramiko.SSHClient.connect')
    async def test_new_command_created(self, admin_user, admin_client):
        device_conn = await database_sync_to_async(self._create_device_connection)()
        communicator = await self._get_communicator(admin_client, device_conn.device_id)
        command = await self._create_command(device_conn)
        response = await communicator.receive_json_from()
        expected_response = self._get_expected_response(command)
        assert response == expected_response
        await communicator.disconnect()

    async def test_multiple_connections_receive_updates_with_redis(
        self, admin_user, admin_client, settings
    ):
        settings.CHANNEL_LAYERS = {
            'default': {
                'BACKEND': 'channels_redis.core.RedisChannelLayer',
                'CONFIG': {
                    'hosts': [('localhost', 6379)],
                },
            },
        }

        device_conn = await database_sync_to_async(self._create_device_connection)()
        communicator1 = await self._get_communicator(
            admin_client, device_conn.device_id
        )
        communicator2 = await self._get_communicator(
            admin_client, device_conn.device_id
        )
        command = await self._create_command(device_conn)
        response1 = await communicator1.receive_json_from()
        response2 = await communicator2.receive_json_from()
        expected_response = self._get_expected_response(command)
        assert response1 == expected_response
        assert response2 == expected_response
        await communicator1.disconnect()
        await communicator2.disconnect()
