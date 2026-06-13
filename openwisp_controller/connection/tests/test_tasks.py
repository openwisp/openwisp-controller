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
