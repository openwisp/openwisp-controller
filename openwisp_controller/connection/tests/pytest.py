from unittest import mock
from uuid import uuid4

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.utils import timezone
from django.utils.module_loading import import_string
from swapper import load_model

from openwisp_controller.connection.tests.utils import CreateCommandMixin

from .. import handlers
from ..channels.consumers import BatchCommandConsumer
from .test_models import BaseTestModels

User = get_user_model()
Command = load_model("connection", "Command")
BatchCommand = load_model("connection", "BatchCommand")
OrganizationUser = load_model("openwisp_users", "OrganizationUser")


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCommandsConsumer(BaseTestModels, CreateCommandMixin):
    application = import_string(getattr(settings, "ASGI_APPLICATION"))

    async def _get_communicator(self, admin_client, device_id):
        session_id = admin_client.cookies["sessionid"].value
        communicator = WebsocketCommunicator(
            self.application,
            path=f"ws/controller/device/{device_id}/command",
            headers=[
                (
                    b"cookie",
                    f"sessionid={session_id}".encode("ascii"),
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
            type="custom",
            input={"command": "echo test"},
        )
        await database_sync_to_async(command.full_clean)()
        with mock.patch("paramiko.SSHClient.exec_command") as mocked_exec_command:
            mocked_exec_command.return_value = self._exec_command_return_value(
                stdout="test"
            )
            await database_sync_to_async(command.save)()
            await database_sync_to_async(command.refresh_from_db)()
        return command

    def _get_expected_response(self, command):
        return {
            "model": "Command",
            "data": {
                "id": str(command.id),
                "created": timezone.localtime(command.created).isoformat(),
                "modified": timezone.localtime(command.modified).isoformat(),
                "status": command.status,
                "type": "Custom commands",
                "input": command.input_data,
                "output": command.output,
                "device": str(command.device_id),
                "connection": str(command.connection_id),
                "batch_command": None,
            },
        }

    @mock.patch("paramiko.SSHClient.connect")
    async def test_new_command_created(self, mocked_connect, admin_user, admin_client):
        device_conn = await database_sync_to_async(self._create_device_connection)()
        communicator = await self._get_communicator(admin_client, device_conn.device_id)
        command = await self._create_command(device_conn)
        response = await communicator.receive_json_from()
        expected_response = self._get_expected_response(command)
        assert response == expected_response
        await communicator.disconnect()

    @mock.patch("paramiko.SSHClient.connect")
    async def test_multiple_connections_receive_updates_with_redis(
        self, mocked_connect, admin_user, admin_client, settings
    ):
        settings.CHANNEL_LAYERS = {
            "default": {
                "BACKEND": "channels_redis.core.RedisChannelLayer",
                "CONFIG": {
                    "hosts": [("localhost", 6379)],
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


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestBatchCommandConsumer(BaseTestModels, CreateCommandMixin):
    application = import_string(getattr(settings, "ASGI_APPLICATION"))
    path = "ws/controller/batch-command"

    async def _connect(self, pk, user=None):
        communicator = WebsocketCommunicator(
            BatchCommandConsumer.as_asgi(), f"{self.path}/{pk}"
        )
        communicator.scope["url_route"] = {"kwargs": {"pk": str(pk)}}
        if user is not None:
            communicator.scope["user"] = user
        connected, _ = await communicator.connect()
        return communicator, connected

    @database_sync_to_async
    def _create_batch(self, organization=None, **kwargs):
        return self._create_batch_command(organization=organization, **kwargs)

    @database_sync_to_async
    def _create_staff(self, username, org=None, codenames=(), is_staff=True):
        user = self._create_user(
            username=username, email=f"{username}@test.com", is_staff=is_staff
        )
        user.user_permissions.set(Permission.objects.filter(codename__in=codenames))
        if org is not None:
            OrganizationUser.objects.create(user=user, organization=org, is_admin=True)
        return User.objects.get(pk=user.pk)

    @database_sync_to_async
    def _set_skipped(self, batch, count):
        batch.skipped_devices = {
            str(uuid4()): {"name": f"skipped{index}", "error": f"error {index}"}
            for index in range(count)
        }
        batch.save(update_fields=["skipped_devices"])
        batch.refresh_from_db(fields=["skipped_devices"])
        return batch.skipped_devices

    async def test_batch_command_consumer_authorization(self, admin_user, admin_client):
        async def connect_through_route(batch):
            session_id = admin_client.cookies["sessionid"].value
            communicator = WebsocketCommunicator(
                self.application,
                path=f"{self.path}/{batch.pk}",
                headers=[(b"cookie", f"sessionid={session_id}".encode("ascii"))],
            )
            connected, _ = await communicator.connect()
            return communicator, connected

        org = await database_sync_to_async(self._get_org)()
        org2 = await database_sync_to_async(self._create_org)(name="org2", slug="org2")
        batch = await self._create_batch(organization=org)
        communicator, connected = await connect_through_route(batch)
        assert connected is True
        await communicator.disconnect()
        communicator, connected = await self._connect(batch.pk)
        assert connected is False
        communicator, connected = await self._connect(batch.pk, AnonymousUser())
        assert connected is False
        communicator, connected = await self._connect(batch.pk, admin_user)
        assert connected is True
        await communicator.disconnect()
        manager = await self._create_staff(
            "manager", org=org, codenames=["view_batchcommand", "add_batchcommand"]
        )
        communicator, connected = await self._connect(batch.pk, manager)
        assert connected is True
        await communicator.disconnect()
        add_only = await self._create_staff(
            "add-only", org=org, codenames=["add_batchcommand"]
        )
        communicator, connected = await self._connect(batch.pk, add_only)
        assert connected is False
        outsider = await self._create_staff(
            "outsider", org=org2, codenames=["view_batchcommand"]
        )
        communicator, connected = await self._connect(batch.pk, outsider)
        assert connected is False
        non_staff = await self._create_staff(
            "non-staff", org=org, codenames=["view_batchcommand"], is_staff=False
        )
        communicator, connected = await self._connect(batch.pk, non_staff)
        assert connected is False
        # a batch without an organization spans every organization
        shared_batch = await self._create_batch(organization=None)
        communicator, connected = await self._connect(shared_batch.pk, manager)
        assert connected is False
        communicator, connected = await self._connect(shared_batch.pk, admin_user)
        assert connected is True
        await communicator.disconnect()
        communicator, connected = await self._connect(uuid4(), manager)
        assert connected is False
        # a rejected connection was never added to a group
        await communicator.disconnect()

    @mock.patch("paramiko.SSHClient.connect")
    async def test_batch_command_consumer_current_state(
        self, mocked_connect, admin_user
    ):
        org = await database_sync_to_async(self._get_org)()
        device_conn = await database_sync_to_async(self._create_device_connection)()
        batch = await self._create_batch(organization=org)
        with mock.patch.object(Command, "_schedule_command"):
            command = await database_sync_to_async(Command.objects.create)(
                batch_command=batch,
                device=device_conn.device,
                connection=device_conn,
                type="custom",
                input={"command": "echo test"},
                status="success",
                output="line one\nline two",
            )
        skipped_pks = list(await self._set_skipped(batch, 3))
        await database_sync_to_async(batch.refresh_from_db)()
        communicator, connected = await self._connect(batch.pk, admin_user)
        assert connected is True
        with mock.patch.object(BatchCommandConsumer, "per_page", 2):
            await communicator.send_json_to(
                {"type": "request_current_state", "page": 1}
            )
            page1 = await communicator.receive_json_from()
            assert page1["type"] == "batch_state"
            assert page1["total_rows"] == 4
            batch_status = page1["batch_status"]
            assert batch_status["status"] == batch.status
            assert "status_display" not in batch_status
            assert batch_status["affected_devices"] == 1
            assert batch_status["skipped_count"] == 3
            assert [row["device"] for row in batch_status["skipped_preview"]] == (
                skipped_pks
            )
            assert "skipped_devices" not in batch_status
            assert [row["device"] for row in page1["commands"]] == [
                str(command.device_id),
                skipped_pks[0],
            ]
            command_row = page1["commands"][0]
            assert command_row["device_name"] == device_conn.device.name
            assert command_row["status"] == command.status
            assert "status_display" not in command_row
            assert command_row["output"] == "… line two"
            assert (
                command_row["modified"]
                == timezone.localtime(command.modified).isoformat()
            )
            assert "input" not in command_row
            await communicator.send_json_to(
                {"type": "request_current_state", "page": 2}
            )
            page2 = await communicator.receive_json_from()
            assert [row["device"] for row in page2["commands"]] == skipped_pks[1:]
            assert all(row["is_skipped"] for row in page2["commands"])
            await communicator.send_json_to(
                {"type": "request_current_state", "page": 3}
            )
            clamped_page = await communicator.receive_json_from()
            assert clamped_page["page"] == 2
            assert clamped_page["commands"] == page2["commands"]
            await communicator.send_json_to(
                {
                    "type": "request_current_state",
                    "page": 1,
                    "filters": {"group_id": str(uuid4())},
                }
            )
            filtered = await communicator.receive_json_from()
            assert filtered["total_rows"] == 0
            assert filtered["commands"] == []
            for field_name in ("group_id", "location_id", "organization_id"):
                await communicator.send_json_to(
                    {
                        "type": "request_current_state",
                        "page": 1,
                        "filters": {field_name: "not-a-uuid"},
                    }
                )
                response = await communicator.receive_json_from()
                assert response["commands"] == page1["commands"]
            for value in ([1], "abc", 7):
                await communicator.send_json_to(
                    {"type": "request_current_state", "page": 1, "filters": value}
                )
                response = await communicator.receive_json_from()
                assert response["type"] == "batch_state"
                assert response["total_rows"] == page1["total_rows"]
            for page in (0, -1, "abc", None):
                await communicator.send_json_to(
                    {"type": "request_current_state", "page": page}
                )
                response = await communicator.receive_json_from()
                assert response["commands"] == page1["commands"]
        await communicator.disconnect()
        communicator, connected = await self._connect(batch.pk, admin_user)
        assert connected is True
        await communicator.send_json_to({"type": "request_current_state"})
        response = await communicator.receive_json_from()
        assert response["total_rows"] == 4
        assert [row["device"] for row in response["commands"]] == [
            str(command.device_id)
        ] + skipped_pks
        # a batch deleted after the connection was accepted is not answered
        await database_sync_to_async(BatchCommand.objects.filter(pk=batch.pk).delete)()
        await communicator.send_json_to({"type": "request_current_state"})
        assert await communicator.receive_nothing() is True
        await communicator.disconnect()

    async def test_batch_command_consumer_access_revoked(self, admin_user):
        org = await database_sync_to_async(self._get_org)()
        batch = await self._create_batch(organization=org)

        def push_batch_status():
            batch.status = "in-progress"
            batch.save(update_fields=["status"])

        manager = await self._create_staff(
            "revoked-manager", org=org, codenames=["view_batchcommand"]
        )

        communicator, connected = await self._connect(batch.pk, manager)
        assert connected is True
        await database_sync_to_async(manager.user_permissions.clear)()
        await communicator.send_json_to({"type": "request_current_state", "page": 1})
        assert await communicator.receive_output() == {"type": "websocket.close"}
        await communicator.disconnect()

        await database_sync_to_async(manager.user_permissions.set)(
            await database_sync_to_async(list)(
                Permission.objects.filter(codename="view_batchcommand")
            )
        )
        communicator, connected = await self._connect(batch.pk, manager)
        assert connected is True
        await database_sync_to_async(
            OrganizationUser.objects.filter(user=manager, organization=org).delete
        )()
        await database_sync_to_async(push_batch_status)()
        assert await communicator.receive_output() == {"type": "websocket.close"}
        await communicator.disconnect()

    async def test_batch_command_consumer_invalid_messages(self, admin_user):
        org = await database_sync_to_async(self._get_org)()
        batch = await self._create_batch(organization=org)
        communicator, connected = await self._connect(batch.pk, admin_user)
        assert connected is True
        with mock.patch(
            "openwisp_controller.connection.channels.consumers.logger"
        ) as logger:
            for message in ("not json", "[]", '"string"', "null"):
                await communicator.send_to(text_data=message)
                assert await communicator.receive_nothing() is True
            for message in ({"type": "unknown"}, {}):
                await communicator.send_json_to(message)
                assert await communicator.receive_nothing() is True
            await communicator.send_to(bytes_data=b"\x00\x01")
            assert await communicator.receive_nothing() is True
            assert logger.warning.call_count == 7
        await communicator.disconnect()

    @mock.patch("paramiko.SSHClient.connect")
    async def test_batch_command_consumer_updates(self, mocked_connect, admin_user):
        async def drain(communicator):
            while not await communicator.receive_nothing():
                await communicator.receive_json_from()

        async def receive_until(communicator, message_type, limit=4):
            for _ in range(limit):
                message = await communicator.receive_json_from()
                if message.get("type") == message_type:
                    return message
            raise AssertionError(f"{message_type} was never received")

        org = await database_sync_to_async(self._get_org)()
        device_conn = await database_sync_to_async(self._create_device_connection)()
        batch = await self._create_batch(organization=org)
        other_batch = await self._create_batch(organization=org, label="other")
        communicator, connected = await self._connect(batch.pk, admin_user)
        assert connected is True
        other, other_connected = await self._connect(other_batch.pk, admin_user)
        assert other_connected is True
        watcher, watcher_connected = await self._connect(batch.pk, admin_user)
        assert watcher_connected is True
        with mock.patch.object(Command, "_schedule_command"):
            command = await database_sync_to_async(Command.objects.create)(
                batch_command=batch,
                device=device_conn.device,
                connection=device_conn,
                type="custom",
                input={"command": "echo test"},
            )
        created = await receive_until(communicator, "command_update")
        assert created["id"] == str(command.pk)
        assert created["status"] == command.status
        assert "status_display" not in created
        assert created["modified"] == timezone.localtime(command.modified).isoformat()
        assert created["index"] == 0
        assert created["affected_devices"] == 1
        assert created["total_rows"] == 1
        assert created["device_name"] == device_conn.device.name
        assert "input" not in created
        assert await receive_until(watcher, "command_update") == created
        assert await communicator.receive_nothing() is True
        command.status = "success"
        command.output = "done"
        await database_sync_to_async(command.save)()
        updated = await receive_until(communicator, "command_update")
        assert updated["status"] == "success"
        assert updated["output"] == "done"
        assert "index" not in updated
        await drain(communicator)
        skipped = await self._set_skipped(batch, 2)
        status = await receive_until(communicator, "batch_status")
        assert status["skipped_count"] == 2
        assert [row["device_name"] for row in status["skipped_preview"]] == [
            row["name"] for row in skipped.values()
        ]
        assert status["affected_devices"] == 1
        assert status["total_rows"] == 3
        # updates are namespaced per batch
        assert await other.receive_nothing() is True
        with mock.patch.object(
            handlers.layers, "get_channel_layer", side_effect=RuntimeError("no layer")
        ), mock.patch.object(handlers, "logger") as logger, mock.patch.object(
            Command, "_schedule_command"
        ):
            await database_sync_to_async(Command.objects.create)(
                batch_command=batch,
                device=device_conn.device,
                connection=device_conn,
                type="custom",
                input={"command": "echo test"},
            )
            logger.exception.assert_called_once()
        assert await database_sync_to_async(batch.batch_commands.count)() == 2
        await communicator.disconnect()
        await watcher.disconnect()
        await other.disconnect()
