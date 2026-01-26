import uuid
from contextlib import redirect_stderr
from io import StringIO
from unittest import mock

from celery.exceptions import SoftTimeLimitExceeded
from django.test import TestCase, TransactionTestCase
from swapper import load_model

from ...config.tests.test_controller import TestRegistrationMixin
from .. import tasks
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
    @mock.patch('openwisp_controller.connection.tasks.current_task')
    @mock.patch('openwisp_controller.connection.tasks.current_app')
    def test_is_update_in_progress_same_worker(self, mocked_current_app, mocked_current_task):
        device_id = 1
        mocked_current_task.request.id = 'task123'
        mocked_inspect = mock.Mock()
        mocked_current_app.control.inspect.return_value = mocked_inspect
        mocked_inspect.active.return_value = {
            'worker1': [
                {'name': 'openwisp_controller.connection.tasks.update_config', 'args': ['1'], 'id': 'task123'}
            ]
        }
        result = tasks._is_update_in_progress(device_id)
        self.assertFalse(result)

    @mock.patch('openwisp_controller.connection.tasks.current_task')
    @mock.patch('openwisp_controller.connection.tasks.current_app')
    def test_is_update_in_progress_different_worker(self, mocked_current_app, mocked_current_task):
        device_id = 1
        mocked_current_task.request.id = 'task123'
        mocked_inspect = mock.Mock()
        mocked_current_app.control.inspect.return_value = mocked_inspect
        mocked_inspect.active.return_value = {
            'worker2': [
                {'name': 'openwisp_controller.connection.tasks.update_config', 'args': ['1'], 'id': 'task456'}
            ]
        }
        result = tasks._is_update_in_progress(device_id)
        self.assertTrue(result)

    @mock.patch('openwisp_controller.connection.tasks.current_task')
    @mock.patch('openwisp_controller.connection.tasks.current_app')
    def test_is_update_in_progress_no_active_tasks(self, mocked_current_app, mocked_current_task):
        device_id = 1
        mocked_current_task.request.id = 'task123'
        mocked_inspect = mock.Mock()
        mocked_current_app.control.inspect.return_value = mocked_inspect
        mocked_inspect.active.return_value = {}
        result = tasks._is_update_in_progress(device_id)
        self.assertFalse(result)

    @mock.patch('openwisp_controller.connection.tasks.current_task')
    @mock.patch('openwisp_controller.connection.tasks.current_app')
    def test_is_update_in_progress_different_device(self, mocked_current_app, mocked_current_task):
        device_id = 1
        mocked_current_task.request.id = 'task123'
        mocked_inspect = mock.Mock()
        mocked_current_app.control.inspect.return_value = mocked_inspect
        mocked_inspect.active.return_value = {
            'worker1': [
                {'name': 'openwisp_controller.connection.tasks.update_config', 'args': ['2'], 'id': 'task456'}
            ]
        }
        result = tasks._is_update_in_progress(device_id)
        self.assertFalse(result)


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
