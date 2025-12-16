import uuid
from contextlib import redirect_stderr
from io import StringIO
from unittest import mock

from celery.exceptions import SoftTimeLimitExceeded
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from swapper import load_model

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


class TestTransactionTasks(CreateConnectionsMixin, TransactionTestCase):
    @mock.patch.object(tasks.update_config, "delay")
    def test_update_config_hostname_changed_on_reregister(self, mocked_update_config):
        org = self._get_org()
        config_settings = OrganizationConfigSettings.objects.create(
            organization=org, context={}, shared_secret="secret"
        )
        device = self._create_device(
            name="AA-BB-CC-DD-EE-FF", organization=org, key="test-key"
        )
        self._create_config(device=device)
        self._create_device_connection(device=device)
        # Trigger re-registration with new hostname
        response = self.client.post(
            reverse("controller:device_register"),
            {
                "name": "new-hostname",
                "secret": str(config_settings.shared_secret),
                "key": str(device.key),
                "mac_address": device.mac_address,
                "backend": "netjsonconfig.OpenWrt",
            },
        )
        self.assertEqual(response.status_code, 201)
        mocked_update_config.assert_not_called()
