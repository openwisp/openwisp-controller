import json
import uuid
from contextlib import redirect_stderr
from io import StringIO
from unittest import mock

from celery.exceptions import SoftTimeLimitExceeded
from django.db import DatabaseError
from django.test import TestCase, TransactionTestCase
from swapper import load_model

from ...config.tests.test_controller import TestRegistrationMixin
from .. import tasks
from ..connectors.exceptions import CommandTimeoutException
from .utils import CreateConnectionsMixin

Command = load_model("connection", "Command")
DeviceConnection = load_model("connection", "DeviceConnection")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")
BatchCommand = load_model("connection", "BatchCommand")


class TestTasks(CreateConnectionsMixin, TestCase):
    _mock_execute = "openwisp_controller.connection.base.models.AbstractCommand.execute"
    _mock_connect = (
        "openwisp_controller.connection.base.models.AbstractDeviceConnection.connect"
    )

    def _get_mocked_celery_active(self, device_id, task_id=None):
        return {
            "worker1": [
                {
                    "name": tasks._TASK_NAME,
                    "args": [device_id],
                    "id": task_id or str(uuid.uuid4()),
                }
            ]
        }

    def test_is_update_in_progress_same_task(self):
        device_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        with mock.patch(
            "celery.app.control.Inspect.active",
            return_value=self._get_mocked_celery_active(device_id, task_id),
        ):
            result = tasks._is_update_in_progress(device_id, current_task_id=task_id)
            self.assertEqual(result, False)

    def test_is_update_in_progress_different_task(self):
        device_id = str(uuid.uuid4())
        current_task_id = str(uuid.uuid4())
        other_task_id = str(uuid.uuid4())
        with mock.patch(
            "celery.app.control.Inspect.active",
            return_value=self._get_mocked_celery_active(device_id, other_task_id),
        ):
            result = tasks._is_update_in_progress(
                device_id, current_task_id=current_task_id
            )
            self.assertEqual(result, True)

    def test_is_update_in_progress_no_tasks(self):
        device_id = str(uuid.uuid4())
        with mock.patch("celery.app.control.Inspect.active", return_value={}):
            result = tasks._is_update_in_progress(device_id)
            self.assertEqual(result, False)

    def test_is_update_in_progress_different_device(self):
        device_id = str(uuid.uuid4())
        other_device_id = str(uuid.uuid4())
        with mock.patch(
            "celery.app.control.Inspect.active",
            return_value=self._get_mocked_celery_active(other_device_id),
        ):
            result = tasks._is_update_in_progress(device_id)
            self.assertEqual(result, False)

    @mock.patch("logging.Logger.warning")
    @mock.patch("time.sleep")
    def test_update_config_missing_config(self, mocked_sleep, mocked_warning):
        pk = self._create_device().pk
        tasks.update_config.delay(pk)
        mocked_warning.assert_called_with(
            f'update_config("{pk}") failed: Device has no config.'
        )
        mocked_sleep.assert_called_once()

    @mock.patch("logging.Logger.warning")
    @mock.patch("time.sleep")
    def test_update_config_missing_device(self, mocked_sleep, mocked_warning):
        pk = uuid.uuid4()
        tasks.update_config.delay(pk)
        mocked_warning.assert_called_with(
            f'update_config("{pk}") failed: Device matching query does not exist.'
        )
        mocked_sleep.assert_called_once()

    @mock.patch("openwisp_controller.connection.tasks.logger.info")
    @mock.patch("time.sleep")
    def test_update_config_skipped_for_deactivated_device(
        self, mocked_sleep, mocked_info
    ):
        dc = self._create_device_connection()
        device = dc.device
        device.deactivate()
        self.assertTrue(device.is_fully_deactivated())
        with mock.patch.object(
            DeviceConnection, "get_working_connection"
        ) as mocked_get_working_connection:
            tasks.update_config.delay(device.pk)
        mocked_get_working_connection.assert_not_called()
        mocked_sleep.assert_called_once()
        mocked_info.assert_called_with(
            f"{device} (pk: {device.pk}) is deactivated, skipping update"
        )

    @mock.patch("logging.Logger.warning")
    def test_launch_command_missing(self, mocked_warning):
        pk = uuid.uuid4()
        tasks.launch_command.delay(pk)
        mocked_warning.assert_called_with(
            f'launch_command("{pk}") failed: Command matching query does not exist.'
        )

    @mock.patch(_mock_execute, side_effect=SoftTimeLimitExceeded())
    @mock.patch(_mock_connect, return_value=True)
    def test_launch_command_timeout(self, *args):
        dc = self._create_device_connection()
        command = Command(
            device=dc.device,
            connection=dc,
            type="custom",
            input={"command": "/usr/sbin/exotic_command"},
        )
        command.full_clean()
        command.save()
        # must call this explicitly because lack of transactions in this test case
        tasks.launch_command.delay(command.pk)
        command.refresh_from_db()
        self.assertEqual(command.status, "failed")
        self.assertEqual(command.output, "Background task time limit exceeded.\n")

    @mock.patch(
        _mock_execute,
        side_effect=CommandTimeoutException("connection timed out after 30s"),
    )
    @mock.patch(_mock_connect, return_value=True)
    def test_launch_command_ssh_timeout(self, *args):
        dc = self._create_device_connection()
        command = Command(
            device=dc.device,
            connection=dc,
            type="custom",
            input={"command": "/usr/sbin/exotic_command"},
        )
        command.full_clean()
        command.save()
        # must call this explicitly because lack of transactions in this test case
        tasks.launch_command.delay(command.pk)
        command.refresh_from_db()
        self.assertEqual(command.status, "failed")
        self.assertEqual(
            command.output,
            "The command took longer than expected: connection timed out after 30s\n",
        )

    @mock.patch(_mock_execute, side_effect=RuntimeError("test error"))
    @mock.patch(_mock_connect, return_value=True)
    def test_launch_command_exception(self, *args):
        dc = self._create_device_connection()
        command = Command(
            device=dc.device,
            connection=dc,
            type="custom",
            input={"command": "/usr/sbin/exotic_command"},
        )
        command.full_clean()
        command.save()
        # must call this explicitly because lack of transactions in this test case
        with redirect_stderr(StringIO()) as stderr:
            tasks.launch_command.delay(command.pk)
            expected = f"An exception was raised while executing command {command.pk}"
            self.assertIn(expected, stderr.getvalue())
        command.refresh_from_db()
        self.assertEqual(command.status, "failed")
        self.assertEqual(command.output, "Internal system error: test error\n")

    def test_launch_command_failure_cleans_change_password_input(self):
        dc = self._create_device_connection()
        password = "SuperSecret123"
        errors = (
            SoftTimeLimitExceeded(),
            CommandTimeoutException("connection timed out after 30s"),
            RuntimeError("test error"),
        )
        for error in errors:
            with self.subTest(type(error).__name__):
                command = Command(
                    device=dc.device,
                    connection=dc,
                    type="change_password",
                    input={"password": password, "confirm_password": password},
                )
                command.full_clean()
                command.save()
                with mock.patch.object(Command, "execute", side_effect=error):
                    with redirect_stderr(StringIO()):
                        tasks.launch_command(command.pk)
                command.refresh_from_db()
                self.assertNotIn(password, json.dumps(command.input))

    @mock.patch(
        "openwisp_controller.connection.base.models.AbstractCommand._exec_command"
    )
    def test_launch_command_deactivating_device_not_blocked(self, mocked_exec_command):
        mocked_exec_command.return_value = 0
        dc = self._create_device_connection()
        command = Command(
            device=dc.device,
            connection=dc,
            type="custom",
            input={"command": "/usr/sbin/exotic_command"},
        )
        command.full_clean()
        command.save()
        # Device deactivation has started but config is still deactivating
        dc.device._is_deactivated = True
        dc.device.save(update_fields=["_is_deactivated"])
        dc.device.config.set_status_deactivating()
        tasks.launch_command.delay(command.pk)
        command.refresh_from_db()
        self.assertNotEqual(command.output, "Device is deactivated.\n")
        mocked_exec_command.assert_called_once()

    @mock.patch(
        "openwisp_controller.connection.base.models.AbstractCommand._exec_command"
    )
    def test_launch_command_deactivated_device(self, mocked_exec_command):
        dc = self._create_device_connection()
        command = Command(
            device=dc.device,
            connection=dc,
            type="custom",
            input={"command": "/usr/sbin/exotic_command"},
        )
        command.full_clean()
        command.save()
        dc.device.deactivate()
        tasks.launch_command.delay(command.pk)
        command.refresh_from_db()
        self.assertEqual(command.status, "failed")
        self.assertEqual(command.output, "Device is deactivated.\n")
        mocked_exec_command.assert_not_called()


class TestTransactionTasks(
    TestRegistrationMixin, CreateConnectionsMixin, TransactionTestCase
):
    @mock.patch.object(tasks.update_config, "delay")
    def test_update_config_hostname_changed_on_reregister(self, mocked_update_config):
        device = self._create_device_config()
        self._create_device_connection(device=device)
        # Trigger re-registration with new hostname
        response = self.client.post(
            self.register_url,
            self._get_reregistration_payload(
                device,
                name="new-hostname",
            ),
        )
        self.assertEqual(response.status_code, 201)
        mocked_update_config.assert_not_called()

    @mock.patch("paramiko.SSHClient.connect", side_effect=Exception("boom"))
    def test_connect_does_not_resurrect_deleted_connection(self, *args):
        # A background command (launch_command) can run against a connection
        # whose row was already deleted by a concurrent deletion or test
        # teardown. connect() records the attempt with save(); it must not
        # resurrect the deleted row (an INSERT with a dangling device FK),
        # which used to surface as flaky "FOREIGN KEY constraint failed".
        DeviceConnection = load_model("connection", "DeviceConnection")
        dc = self._create_device_connection()
        DeviceConnection.objects.filter(pk=dc.pk).delete()
        dc.connect()
        self.assertFalse(DeviceConnection.objects.filter(pk=dc.pk).exists())

    @mock.patch("paramiko.SSHClient.connect", side_effect=Exception("boom"))
    def test_connect_reraises_genuine_db_error(self, *args):
        # Only the deleted-row case is ignored: a real database write failure
        # while the connection still exists must be re-raised, not swallowed.
        DeviceConnection = load_model("connection", "DeviceConnection")
        dc = self._create_device_connection()
        with mock.patch.object(
            DeviceConnection, "save", side_effect=DatabaseError("boom")
        ):
            with self.assertRaises(DatabaseError):
                dc.connect()

    @mock.patch("paramiko.SSHClient.connect")
    def test_execute_skips_deleted_command(self, *args):
        # A command deleted after being scheduled (e.g. racing a deletion or a
        # test teardown) must not be sent to the device and must not be
        # resurrected by its trailing save (whose FK error can corrupt the
        # live-server DB during selenium tests).
        with mock.patch("openwisp_controller.connection.base.models.launch_command"):
            dc = self._create_device_connection()
            command = Command(
                device=dc.device,
                connection=dc,
                type="custom",
                input={"command": "echo test"},
            )
            command.full_clean()
            command.save()
        Command.objects.filter(pk=command.pk).delete()
        with mock.patch.object(command, "_exec_command") as mocked_exec:
            command.execute()
        mocked_exec.assert_not_called()
        self.assertFalse(Command.objects.filter(pk=command.pk).exists())

    @mock.patch("paramiko.SSHClient.connect")
    def test_launch_command_handler_does_not_resurrect_deleted_command(self, *args):
        # If the command is deleted while execute() runs and execute() then
        # raises, launch_command's exception handler must not resurrect it.
        with mock.patch("openwisp_controller.connection.base.models.launch_command"):
            dc = self._create_device_connection()
            command = Command(
                device=dc.device,
                connection=dc,
                type="custom",
                input={"command": "echo test"},
            )
            command.full_clean()
            command.save()

        def _delete_then_raise(self):
            Command.objects.filter(pk=self.pk).delete()
            raise RuntimeError("boom")

        with mock.patch.object(Command, "execute", _delete_then_raise):
            tasks.launch_command(command.pk)
        self.assertFalse(Command.objects.filter(pk=command.pk).exists())

    @mock.patch("logging.Logger.warning")
    def test_launch_batch_command_skips_deleted_batch(self, mocked_warning):
        batch_id = uuid.uuid4()
        tasks.launch_batch_command(batch_id=batch_id)
        mocked_warning.assert_called_with(
            f"The BatchCommand object with id {batch_id} has been deleted"
        )

    @mock.patch("openwisp_controller.connection.tasks.launch_command.delay")
    def test_launch_batch_command_creates_commands(self, mocked_delay):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)
        self._create_device_connection(device=device)
        batch = BatchCommand(
            organization=org,
            type="custom",
            input={"command": "echo 'test'"},
            label="test-label",
        )
        batch.full_clean()
        batch.save()
        batch.devices.set([device])
        tasks.launch_batch_command(batch_id=batch.pk)
        batch.refresh_from_db()
        self.assertEqual(batch.batch_commands.count(), 1)
        command = batch.batch_commands.first()
        self.assertEqual(command.device, device)
        self.assertEqual(command.type, batch.type)
        self.assertEqual(command.status, "in-progress")
        mocked_delay.assert_called_once_with(command.pk)

    @mock.patch("openwisp_controller.connection.tasks.launch_command.delay")
    def test_launch_batch_command_creates_commands_for_multiple_devices(
        self, mocked_delay
    ):
        org = self._get_org()
        cred = self._create_credentials(organization=org, name="Multi device cred")
        devices = []
        for i in range(2):
            d = self._create_device(
                name=f"task-dev-{i}",
                mac_address=f"00:11:22:33:44:{i + 0x50:02x}",
                organization=org,
            )
            self._create_config(device=d)
            self._create_device_connection(device=d, credentials=cred)
            devices.append(d)
        batch = BatchCommand(
            organization=org,
            type="custom",
            input={"command": "echo test"},
            label="test-label",
        )
        batch.full_clean()
        batch.save()
        batch.devices.set(devices)
        tasks.launch_batch_command(batch_id=batch.pk)
        batch.refresh_from_db()
        self.assertEqual(batch.batch_commands.count(), 2)
        cmd_devices = [c.device for c in batch.batch_commands.all()]
        for d in devices:
            self.assertIn(d, cmd_devices)
        self.assertEqual(batch.status, "in-progress")
        self.assertEqual(mocked_delay.call_count, 2)

    @mock.patch(
        "openwisp_controller.connection.base.models.AbstractBatchCommand"
        ".create_commands",
        side_effect=SoftTimeLimitExceeded(),
    )
    def test_launch_batch_command_timeout(self, mocked_create_commands):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)
        batch = BatchCommand(
            organization=org,
            type="custom",
            input={"command": "echo test"},
            label="test-label",
        )
        batch.full_clean()
        batch.save()
        tasks.launch_batch_command(batch_id=batch.pk)
        batch.refresh_from_db()
        self.assertEqual(batch.status, "failed")

    @mock.patch(
        "openwisp_controller.connection.base.models.AbstractBatchCommand"
        ".create_commands",
        side_effect=RuntimeError("test error"),
    )
    def test_launch_batch_command_exception(self, mocked_create_commands):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)

        with self.subTest("custom command"):
            batch = BatchCommand(
                organization=org,
                type="custom",
                input={"command": "echo test"},
                label="test-label",
            )
            batch.full_clean()
            batch.save()
            with redirect_stderr(StringIO()) as stderr:
                tasks.launch_batch_command(batch_id=batch.pk)
                self.assertIn(
                    f"An exception was raised while executing batch command {batch.pk}",
                    stderr.getvalue(),
                )
            batch.refresh_from_db()
            self.assertEqual(batch.status, "failed")

        with self.subTest("change_password input is cleaned up"):
            password = "SuperSecret123"
            batch = BatchCommand(
                organization=org,
                type="change_password",
                input={"password": password, "confirm_password": password},
                label="test-pwd",
            )
            batch.full_clean()
            batch.save()
            tasks.launch_batch_command(batch_id=batch.pk)
            batch.refresh_from_db()
            self.assertEqual(batch.status, "failed")
            self.assertNotIn(password, json.dumps(batch.input))

    @mock.patch("openwisp_controller.connection.tasks.launch_command.delay")
    def test_launch_batch_command_all_devices_skipped(self, mocked_delay):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)
        device.deactivate()
        device.config.set_status_deactivated()
        batch = BatchCommand(
            organization=org,
            type="custom",
            input={"command": "echo test"},
            label="test-label",
        )
        batch.full_clean()
        batch.save()
        batch.devices.set([device])
        tasks.launch_batch_command(batch_id=batch.pk)
        batch.refresh_from_db()
        self.assertEqual(batch.batch_commands.count(), 0)
        self.assertIn(str(device.pk), batch.skipped_devices)
        self.assertEqual(batch.status, "failed")
        mocked_delay.assert_not_called()

    @mock.patch("openwisp_controller.connection.tasks.launch_command.delay")
    def test_launch_batch_command_already_processed(self, mocked_delay):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)
        self._create_device_connection(device=device)
        batch = BatchCommand(
            organization=org,
            type="custom",
            input={"command": "echo test"},
            label="test-label",
        )
        batch.full_clean()
        batch.save()
        batch.devices.set([device])
        # First call — creates commands
        tasks.launch_batch_command(batch_id=batch.pk)
        batch.refresh_from_db()
        self.assertEqual(batch.batch_commands.count(), 1)
        first_call_count = mocked_delay.call_count
        # Second call — should be a no-op (idempotency guard)
        tasks.launch_batch_command(batch_id=batch.pk)
        batch.refresh_from_db()
        self.assertEqual(batch.batch_commands.count(), 1)
        self.assertEqual(mocked_delay.call_count, first_call_count)
