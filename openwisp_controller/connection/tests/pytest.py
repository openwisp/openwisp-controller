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

    @mock.patch('paramiko.SSHClient.connect')
    async def test_new_command_created(self, admin_user, admin_client):
        device_conn = await database_sync_to_async(self._create_device_connection)()
        communicator = await self._get_communicator(admin_client, device_conn.device_id)

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

        response = await communicator.receive_json_from()
        expected_response = {
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
        assert response == expected_response
        await communicator.disconnect()
