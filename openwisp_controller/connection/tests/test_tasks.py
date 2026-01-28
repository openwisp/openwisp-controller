import uuid
from contextlib import redirect_stderr
from io import StringIO
from unittest import mock

from celery.exceptions import SoftTimeLimitExceeded
from django.test import TestCase, TransactionTestCase
from swapper import load_model

from ...config.tests.test_controller import TestRegistrationMixin
from .. import tasks
from ..tasks import _TASK_NAME, _is_update_in_progress
from .utils import CreateConnectionsMixin

Command = load_model("connection", "Command")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")


class TestTasks(CreateConnectionsMixin, TestCase):
    _mock_execute = "openwisp_controller.connection.base.models.AbstractCommand.execute"
    _mock_connect = (
        "openwisp_controller.connection.base.models.AbstractDeviceConnection.connect"
    )

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


class TestIsUpdateInProgress(CreateConnectionsMixin, TestCase):

    def _get_mocked_active_tasks(self, device_id, task_id="task-123"):
        return {
            "celery@worker1": [
                {
                    "id": task_id,
                    "name": _TASK_NAME,
                    "args": f"('{device_id}',)",
                }
            ]
        }

    @mock.patch("openwisp_controller.connection.tasks.current_app")
    def test_is_update_in_progress_without_current_task_id(self, mock_app):

        device_id = uuid.uuid4()
        current_task_id = "task-123"

        mock_app.control.inspect.return_value.active.return_value = (
            self._get_mocked_active_tasks(device_id, task_id=current_task_id)
        )

        # BUG: Without passing current_task_id, the function returns True
        # even though the only active task IS the current task
        result = _is_update_in_progress(device_id)
        self.assertTrue(
            result,
        )

    @mock.patch("openwisp_controller.connection.tasks.current_app")
    def test_is_update_in_progress_with_current_task_id_excluded(self, mock_app):

        device_id = uuid.uuid4()
        current_task_id = "task-123"

        mock_app.control.inspect.return_value.active.return_value = (
            self._get_mocked_active_tasks(device_id, task_id=current_task_id)
        )

        # FIX: With current_task_id provided, the function correctly returns False
        result = _is_update_in_progress(device_id, current_task_id=current_task_id)
        self.assertFalse(
            result,
        )

    @mock.patch("openwisp_controller.connection.tasks.current_app")
    def test_is_update_in_progress_detects_another_task(self, mock_app):

        device_id = uuid.uuid4()
        current_task_id = "task-123"
        another_task_id = "task-456"

        # Mock active tasks with both current task and another task
        mock_app.control.inspect.return_value.active.return_value = {
            "celery@worker1": [
                {
                    "id": current_task_id,
                    "name": _TASK_NAME,
                    "args": f"('{device_id}',)",
                },
                {
                    "id": another_task_id,
                    "name": _TASK_NAME,
                    "args": f"('{device_id}',)",
                },
            ]
        }

        # Should return True because another task IS running
        result = _is_update_in_progress(device_id, current_task_id=current_task_id)
        self.assertTrue(
            result,
        )

    @mock.patch("openwisp_controller.connection.tasks.current_app")
    def test_is_update_in_progress_no_active_tasks(self, mock_app):

        device_id = uuid.uuid4()
        mock_app.control.inspect.return_value.active.return_value = None

        result = _is_update_in_progress(device_id, current_task_id="task-123")
        self.assertFalse(result)

    @mock.patch("openwisp_controller.connection.tasks.current_app")
    def test_is_update_in_progress_different_device(self, mock_app):

        device_id = uuid.uuid4()
        other_device_id = uuid.uuid4()

        mock_app.control.inspect.return_value.active.return_value = (
            self._get_mocked_active_tasks(other_device_id, task_id="task-456")
        )

        result = _is_update_in_progress(device_id, current_task_id="task-123")
        self.assertFalse(
            result,
        )


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
