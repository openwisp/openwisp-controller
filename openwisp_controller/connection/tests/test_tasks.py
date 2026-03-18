import uuid
from contextlib import redirect_stderr
from io import StringIO
from unittest import mock

from celery.exceptions import SoftTimeLimitExceeded
from django.test import TestCase
from swapper import load_model

from .. import tasks
from .utils import CreateConnectionsMixin

Command = load_model("connection", "Command")


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
