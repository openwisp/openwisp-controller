import socket
from unittest import mock
from unittest.mock import PropertyMock
from uuid import uuid4

import paramiko
from django.contrib.auth.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase, TransactionTestCase, tag
from django.utils import timezone
from django.utils.module_loading import import_string
from swapper import load_model

from openwisp_utils.tests import capture_any_output, catch_signal

from .. import handlers
from .. import settings as app_settings
from ..commands import (
    COMMANDS,
    ORGANIZATION_ENABLED_COMMANDS,
    register_command,
    unregister_command,
)
from ..exceptions import NoWorkingDeviceConnectionError
from ..signals import is_working_changed
from ..tasks import _TASK_NAME, update_config
from .utils import CreateConnectionsMixin

Config = load_model("config", "Config")
LOGGER_NAME = "openwisp_controller.connection.base.models"
Device = load_model("config", "Device")
Credentials = load_model("connection", "Credentials")
DeviceConnection = load_model("connection", "DeviceConnection")
Group = load_model("openwisp_users", "Group")
Organization = load_model("openwisp_users", "Organization")
Command = load_model("connection", "Command")
BatchCommand = load_model("connection", "BatchCommand")
DeviceGroup = load_model("config", "DeviceGroup")
Location = load_model("geo", "Location")
DeviceLocation = load_model("geo", "DeviceLocation")

_connect_path = "paramiko.SSHClient.connect"
_exec_command_path = "paramiko.SSHClient.exec_command"


class BaseTestModels(CreateConnectionsMixin):
    app_label = "connection"

    def _exec_command_return_value(
        self, stdin="", stdout="mocked", stderr="", exit_code=0
    ):
        stdin_ = mock.Mock()
        stdout_ = mock.Mock()
        stderr_ = mock.Mock()
        stdin_.read().decode.return_value = stdin
        stdout_.read().decode.return_value = stdout
        type(stdout_.channel).exit_status = PropertyMock(return_value=exit_code)
        stderr_.read().decode.return_value = stderr
        return (stdin_, stdout_, stderr_)


class TestModels(BaseTestModels, TestCase):
    def test_connection_str(self):
        c = Credentials(name="Dev Key", connector=app_settings.CONNECTORS[0][0])
        self.assertIn(c.name, str(c))
        self.assertIn(c.get_connector_display(), str(c))

    def test_device_connection_get_params(self):
        dc = self._create_device_connection()
        self.assertEqual(dc.get_params(), dc.credentials.params)
        dc.params = {"port": 2400}
        self.assertEqual(dc.get_params()["port"], 2400)
        self.assertEqual(dc.get_params()["username"], "root")

    def test_device_connection_auto_update_strategy(self):
        dc = self._create_device_connection()
        self.assertEqual(dc.update_strategy, app_settings.UPDATE_STRATEGIES[0][0])

    def test_device_connection_auto_update_strategy_key_error(self):
        orig_strategy = app_settings.UPDATE_STRATEGIES
        orig_mapping = app_settings.CONFIG_UPDATE_MAPPING
        app_settings.UPDATE_STRATEGIES = (("meddle", "meddle"),)
        app_settings.CONFIG_UPDATE_MAPPING = {"wrong": "wrong"}
        try:
            self._create_device_connection()
        except ValidationError:
            failed = False
        else:
            failed = True
        # restore
        app_settings.UPDATE_STRATEGIES = orig_strategy
        app_settings.CONFIG_UPDATE_MAPPING = orig_mapping
        if failed:
            self.fail("ValidationError not raised")

    def test_device_connection_auto_update_strategy_missing_config(self):
        device = self._create_device(organization=self._get_org())
        self.assertFalse(hasattr(device, "config"))
        try:
            self._create_device_connection(device=device)
        except ValidationError as e:
            self.assertIn("inferred from", str(e))
        else:
            self.fail("ValidationError not raised")

    def test_device_connection_connector_instance(self):
        dc = self._create_device_connection()
        self.assertIsInstance(dc.connector_instance, dc.connector_class)

    def test_device_connection_ssh_rsa_key_param(self):
        ckey = self._create_credentials_with_key()
        dc = self._create_device_connection(credentials=ckey)
        self.assertIn("pkey", dc.connector_instance.params)
        self.assertIsInstance(
            dc.connector_instance.params["pkey"], paramiko.rsakey.RSAKey
        )
        self.assertNotIn("key", dc.connector_instance.params)

    def test_device_connection_ssh_ed22519_key_param(self):
        ckey = self._create_credentials_with_ed_key()
        dc = self._create_device_connection(credentials=ckey)
        self.assertIn("pkey", dc.connector_instance.params)
        self.assertIsInstance(
            dc.connector_instance.params["pkey"], paramiko.ed25519key.Ed25519Key
        )
        self.assertNotIn("key", dc.connector_instance.params)

    @mock.patch.object(DeviceConnection, "connect")
    def test_device_connection_get_working_connection(self, mocked_connect):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)

        with self.subTest("Test device has no connection object"):
            with self.assertRaises(NoWorkingDeviceConnectionError) as error:
                conn = DeviceConnection.get_working_connection(device)
            self.assertEqual(error.exception.connection, None)

        conn1 = self._create_device_connection(
            device=device,
            credentials=self._create_credentials(organization=org, name="test1"),
            is_working=True,
        )
        conn2 = self._create_device_connection(
            device=device,
            credentials=self._create_credentials(organization=org, name="test2"),
            is_working=False,
        )
        self._create_device_connection(
            device=device,
            credentials=self._create_credentials(organization=org, name="test3"),
            is_working=None,
        )

        with self.subTest("Test previously working credential is attempted first"):
            mocked_connect.side_effect = [True]
            conn = DeviceConnection.get_working_connection(device)
            self.assertEqual(conn, conn1)

        with self.subTest("Test attempt with other credentials on failure"):
            mocked_connect.side_effect = [False, True]
            conn = DeviceConnection.get_working_connection(device)
            self.assertEqual(conn, conn2)

        with self.subTest("Test no working credentials"):
            mocked_connect.side_effect = [False, False, False]
            with self.assertRaises(NoWorkingDeviceConnectionError) as error:
                conn = DeviceConnection.get_working_connection(device)
            self.assertNotEqual(error.exception.connection, None)

    @mock.patch(_connect_path)
    def test_update_config_task_use_get_working_connection(self, *args):
        device_conn = self._create_device_connection()
        with mock.patch.object(
            DeviceConnection, "get_working_connection"
        ) as mocked_func:
            update_config.delay(device_conn.device_id)
        mocked_func.assert_called_once_with(device_conn.device)

    def test_credentials_invalid_ssh_key(self):
        invalid_keys = [
            """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABsQAAAAdzc2gtZH
NzAAAAgQCPS4iiaXzTs+VST1o1w6oU2c0IBIAjaM/gmdpuj45F5KKbNuoHxDHxXS7KagML
Lg6Lv7B4I290HR9S2aUVpSW1JhswO28LJz5+zVAIpSjp+aCGv0GqQdFKcZ9gUejZcg1ZTK
OTVDTfojbraBBJDQVJH8IfoPTuQ8R+SEoAgM8euwAAABUAxKPeMdsQKah4zJNjiMkUi4gN
5FkAAACACE33nYpHu+O4naJMIIH62L7i2yKWkccPMk32pq1Iin9dOIjVAUv7U/HKovqqyt
kzvhjCHIZsZBPlR319gw//ywRUbvSbDBZWV16SOMFJNyH8Wcx73FpjokxtTTu83DQMnx37
KpEdLBD3I1BpjWlOY+Hpu4lwsnPWAoNsp4m78dkAAACACFnPy97iwr1ZuimrjcK7aRAOBf
g2gDpb4UKbEIp/kCFgjNhDEirIJrN3syuMLBKjEQ/BaSmAJcOZchclKb9YaJIElljs2ran
C1/KFzpov5rdj4s+asafCNix2ptkj4GKGSQgeV5dR2NK/b7t4B2Wdy6U0vaM6/IWQhqvvM
+mMY4AAAHom2XawZtl2sEAAAAHc3NoLWRzcwAAAIEAj0uIoml807PlUk9aNcOqFNnNCASA
I2jP4Jnabo+OReSimzbqB8Qx8V0uymoDCy4Oi7+weCNvdB0fUtmlFaUltSYbMDtvCyc+fs
1QCKUo6fmghr9BqkHRSnGfYFHo2XINWUyjk1Q036I262gQSQ0FSR/CH6D07kPEfkhKAIDP
HrsAAAAVAMSj3jHbECmoeMyTY4jJFIuIDeRZAAAAgAhN952KR7vjuJ2iTCCB+ti+4tsilp
HHDzJN9qatSIp/XTiI1QFL+1PxyqL6qsrZM74YwhyGbGQT5Ud9fYMP/8sEVG70mwwWVlde
kjjBSTch/FnMe9xaY6JMbU07vNw0DJ8d+yqRHSwQ9yNQaY1pTmPh6buJcLJz1gKDbKeJu/
HZAAAAgAhZz8ve4sK9Wbopq43Cu2kQDgX4NoA6W+FCmxCKf5AhYIzYQxIqyCazd7MrjCwS
oxEPwWkpgCXDmXIXJSm/WGiSBJZY7Nq2pwtfyhc6aL+a3Y+LPmrGnwjYsdqbZI+BihkkIH
leXUdjSv2+7eAdlnculNL2jOvyFkIar7zPpjGOAAAAFHFcD3oAPq5orH1/9tdihL2Gn4Iu
AAAADG5lbWVzaXNAZW52eQECAwQFBgc=
-----END OPENSSH PRIVATE KEY-----""",
            """+mMY4AAAHom2XawZtl2sEAAAAHc3NoLWRzcwAAAIEAj0uIoml807PlUk9aNcOqFNnNCASA
leXUdjSv2+7eAdlnculNL2jOvyFkIar7zPpjGOAAAAFHFcD3oAPq5orH1/9tdihL2Gn4Iu
HZAAAAgAhZz8ve4sK9Wbopq43Cu2kQDgX4NoA6W+FCmxCKf5AhYIzYQxIqyCazd7MrjCwS""",
        ]
        for invalid_key in invalid_keys:
            opts = dict(
                name="Test SSH Key",
                params={"username": "root", "key": invalid_key, "port": 22},
            )
            with self.subTest(f"Testing key {invalid_key}"):
                with self.assertRaises(ValidationError) as ctx:
                    self._create_credentials(**opts)
                self.assertIn("params", ctx.exception.message_dict)
                self.assertIn(
                    "Unrecognized or unsupported SSH key algorithm",
                    str(ctx.exception.message_dict["params"]),
                )

    @mock.patch(_connect_path)
    def test_ssh_connect(self, mocked_connect):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connect()
        mocked_connect.assert_called_once()
        self.assertTrue(dc.is_working)
        self.assertIsNotNone(dc.last_attempt)
        self.assertEqual(dc.failure_reason, "")
        dc.disconnect()

    def test_ssh_connect_failure(self):
        ckey = self._create_credentials_with_key(
            username="wrong", port=self.ssh_server.port
        )
        dc = self._create_device_connection(credentials=ckey)
        dc.device.last_ip = None
        dc.device.save()
        with mock.patch(_connect_path) as mocked_connect:
            mocked_connect.side_effect = Exception("Authentication failed.")
            dc.connect()
            mocked_connect.assert_called_once()
        self.assertEqual(dc.is_working, False)
        self.assertIsNotNone(dc.last_attempt)
        self.assertEqual(dc.failure_reason, "Authentication failed.")

    def test_connect_deactivated_device(self):
        dc = self._create_device_connection()

        with self.subTest("fully deactivated: connect blocked, signal suppressed"):
            dc.device.deactivate()
            self.assertTrue(dc.device.is_fully_deactivated())
            with catch_signal(is_working_changed) as handler:
                dc.connect()
            self.assertEqual(dc.is_working, False)
            self.assertEqual(dc.failure_reason, "Device is deactivated")
            handler.assert_not_called()

        with self.subTest("deactivating: connect allowed through"):
            cred2 = self._create_credentials(name="cred-deactivating")
            device2 = self._create_device(
                name="deactivating-device", mac_address="11:22:33:44:55:66"
            )
            template = self._create_template(organization=device2.organization)
            self._create_config(device=device2, templates=[template])
            dc2 = self._create_device_connection(credentials=cred2, device=device2)
            dc2.device.deactivate()
            self.assertEqual(dc2.device.config.status, "deactivating")
            self.assertEqual(dc2.device.is_fully_deactivated(), False)
            with mock.patch.object(dc2.connector_instance, "connect") as mocked_conn:
                dc2.connect()
            mocked_conn.assert_called_once()

    def test_credentials_schema(self):
        # unrecognized parameter
        try:
            self._create_credentials(
                params={
                    "username": "root",
                    "password": "password",
                    "unrecognized": True,
                }
            )
        except ValidationError as e:
            self.assertIn("params", e.message_dict)
        else:
            self.fail("ValidationError not raised")
        # missing password or key
        try:
            self._create_credentials(params={"username": "root", "port": 22})
        except ValidationError as e:
            self.assertIn("params", e.message_dict)
        else:
            self.fail("ValidationError not raised")

    def test_credentials_connection_missing(self):
        with self.assertRaises(ValidationError) as e:
            c = Credentials(
                name="Test credentials",
                connector=None,
                params={"username": "root", "password": "password", "port": 22},
                organization=self._get_org(),
            )
            c.full_clean()
            self.assertIn("connector", e.message_dict)

    def test_device_connection_schema(self):
        # unrecognized parameter
        try:
            self._create_device_connection(
                params={
                    "username": "root",
                    "password": "password",
                    "unrecognized": True,
                }
            )
        except ValidationError as e:
            self.assertIn("params", e.message_dict)
        else:
            self.fail("ValidationError not raised")

    def _prepare_address_list_test(self, last_ip=None, management_ip=None):
        update_strategy = app_settings.UPDATE_STRATEGIES[0][0]
        device = self._create_device(
            organization=self._get_org(), last_ip=last_ip, management_ip=management_ip
        )
        dc = self._create_device_connection(
            device=device, update_strategy=update_strategy
        )
        return dc

    def test_address_list(self):
        dc = self._prepare_address_list_test()
        self.assertEqual(dc.get_addresses(), [])

    def test_address_list_with_device_ip(self):
        dc = self._prepare_address_list_test(
            management_ip="10.0.0.2", last_ip="84.32.46.153"
        )
        with self.subTest("Test MANAGEMENT_IP_ONLY is set to True"):
            with mock.patch.object(app_settings, "MANAGEMENT_IP_ONLY", True):
                self.assertEqual(dc.get_addresses(), ["10.0.0.2"])

        with self.subTest("Test MANAGEMENT_IP_ONLY is set to False"):
            with mock.patch.object(app_settings, "MANAGEMENT_IP_ONLY", False):
                self.assertEqual(dc.get_addresses(), ["10.0.0.2", "84.32.46.153"])

    def test_device_connection_credential_org_validation(self):
        dc = self._create_device_connection()
        shared = self._create_credentials(name="cred-shared", organization=None)
        dc.credentials = shared
        dc.full_clean()
        # ensure credentials of other orgs aren't accepted
        org2 = self._create_org(name="org2")
        cred2 = self._create_credentials(name="cred2", organization=org2)
        try:
            dc.credentials = cred2
            dc.full_clean()
        except ValidationError as e:
            self.assertIn("credentials", e.message_dict)
        else:
            self.fail("ValidationError not raised")

    def test_device_connection_same_credential_twice(self):
        device_conn = self._create_device_connection()
        with self.assertRaises(ValidationError) as context_manager:
            device_conn = DeviceConnection(
                device=device_conn.device, credentials=device_conn.credentials
            )
            device_conn.full_clean()
        self.assertEqual(
            context_manager.exception.message_dict["__all__"][0],
            "Device connection with this Device and Credentials already exists.",
        )

    def test_auto_add_to_new_device(self):
        c = self._create_credentials(auto_add=True, organization=None)
        self._create_credentials(name="cred2", auto_add=False, organization=None)
        d = self._create_device(organization=Organization.objects.first())
        self._create_config(device=d)
        d.refresh_from_db()
        self.assertEqual(d.deviceconnection_set.count(), 1)
        self.assertEqual(d.deviceconnection_set.first().credentials, c)

    def test_auto_add_to_new_deactivated_device(self):
        org = self._get_org()
        self._create_credentials(auto_add=True, organization=None)
        device = self._create_device(organization=org, name="deactivated-device")
        device.deactivate()
        self._create_config(device=device)
        device.refresh_from_db()
        self.assertEqual(device.deviceconnection_set.count(), 1)

    def test_auto_add_device_missing_config(self):
        org = Organization.objects.first()
        self._create_device(organization=org)
        self._create_credentials(auto_add=True, organization=None)
        self.assertEqual(Credentials.objects.count(), 1)

    @capture_any_output()
    @mock.patch(_connect_path)
    def test_ssh_exec_exit_code(self, *args):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connector_instance.connect()
        with mock.patch(_exec_command_path) as mocked:
            mocked.return_value = self._exec_command_return_value(exit_code=1)
            with self.assertRaises(Exception):
                dc.connector_instance.exec_command("trigger_command_not_found")
            dc.connector_instance.disconnect()
            mocked.assert_called_once()

    @capture_any_output()
    @mock.patch(_connect_path)
    def test_ssh_exec_timeout(self, *args):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connector_instance.connect()
        with mock.patch(_exec_command_path) as mocked:
            mocked.side_effect = socket.timeout()
            with self.assertRaises(socket.timeout):
                dc.connector_instance.exec_command("trigger_timeout")
            dc.connector_instance.disconnect()
            mocked.assert_called_once()

    @capture_any_output()
    @mock.patch(_connect_path)
    def test_ssh_exec_exception(self, *args):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connector_instance.connect()
        with mock.patch(_exec_command_path) as mocked:
            mocked.side_effect = RuntimeError("test")
            with self.assertRaises(RuntimeError):
                dc.connector_instance.exec_command("trigger_exception")
            dc.connector_instance.disconnect()
            mocked.assert_called_once()

    def test_connect_no_addresses(self):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.device.last_ip = None
        dc.device.management_ip = None
        dc.save()
        with self.assertRaises(ValueError):
            dc.connector_instance.connect()

    def test_is_working_change_signal_emitted(self):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        with catch_signal(is_working_changed) as handler:
            dc.is_working = True
            dc.save()
        handler.assert_called_once_with(
            failure_reason="",
            old_failure_reason="",
            instance=dc,
            is_working=True,
            old_is_working=None,
            sender=DeviceConnection,
            signal=is_working_changed,
        )

    def test_operator_group_permissions(self):
        group = Group.objects.get(name="Operator")
        permissions = group.permissions.filter(
            content_type__app_label=f"{self.app_label}"
        )
        self.assertEqual(permissions.count(), 8)

    def test_administrator_group_permissions(self):
        group = Group.objects.get(name="Administrator")
        permissions = group.permissions.filter(
            content_type__app_label=f"{self.app_label}"
        )
        self.assertEqual(permissions.count(), 16)

    def test_device_connection_set_connector(self):
        dc = self._create_device_connection()
        connector = dc.connector_class(
            params=dc.get_params(), addresses=dc.get_addresses()
        )
        connector.IS_MODIFIED = True
        self.assertFalse(hasattr(dc.connector_instance, "IS_MODIFIED"))
        del dc.connector_instance
        dc.set_connector(connector)
        self.assertTrue(hasattr(dc.connector_instance, "IS_MODIFIED"))
        self.assertTrue(dc.connector_instance, "IS_MODIFIED")
        dc.credentials.delete()
        # ensure change not permanent
        org2 = self._create_org(name="org2")
        dev2 = self._create_device(organization=org2)
        self._create_config(device=dev2)
        dc2 = self._create_device_connection(device=dev2)
        self.assertFalse(hasattr(dc2.connector_instance, "IS_MODIFIED"))

    def test_command_str(self):
        with self.subTest("custom command short"):
            command = Command(type="custom", input={"command": "echo test"})
            self.assertIn("«echo test» sent on", str(command))
        with self.subTest("custom command long"):
            cmd = {"command": 'echo "longer than thirtytwo characters"'}
            command = Command(type="custom", input=cmd)
            self.assertIn('«echo "longer than thirtytwo char…»', str(command))
        with self.subTest("predefined command"):
            command = Command(type="reboot")
            created = timezone.localtime(command.created).strftime(
                "%d %b %Y at %I:%M %p"
            )
            self.assertIn("«Reboot» sent on", str(command))
            self.assertIn(created, str(command))

    def test_command_arguments(self):
        with self.subTest("Test arguments for a custom command"):
            command = Command(type="custom", input={"command": "echo test"})
            with self.assertRaises(TypeError):
                command.arguments

        with self.subTest("Test arguments for change password command"):
            command = Command(
                type="change_password",
                input={"password": "Pass@1234", "confirm_password": "Pass@1234"},
            )
            self.assertEqual(list(command.arguments), ["Pass@1234", "Pass@1234"])

    def test_command_is_custom(self):
        command = Command(type="custom", input={"command": "echo test"})
        self.assertTrue(command.is_custom)

    def test_command_output_preview(self):
        with self.subTest("no output"):
            self.assertEqual(Command(type="reboot").output_preview, "")
            self.assertEqual(Command(type="reboot", output="").output_preview, "")

        with self.subTest("single line"):
            command = Command(type="reboot", output="all good")
            self.assertEqual(command.output_preview, "all good")

        with self.subTest("single line with trailing newline"):
            command = Command(type="reboot", output="all good\n")
            self.assertEqual(command.output_preview, "all good")

        with self.subTest("single long line"):
            command = Command(type="reboot", output="x" * 120)
            self.assertEqual(command.output_preview, f"… {'x' * 100}")

        with self.subTest("multiple lines"):
            command = Command(type="reboot", output="first\nsecond\nlast")
            self.assertEqual(command.output_preview, "… last")

        with self.subTest("multiple lines with a long last line"):
            command = Command(type="reboot", output=f"first\n{'y' * 120}")
            self.assertEqual(command.output_preview, f"… {'y' * 100}")

    def test_command_validation(self):
        dc = self._create_device_connection()
        command = Command(
            device=dc.device, type="custom", input={"command": "echo test"}
        )

        with self.subTest("custom type without input raises ValidationError"):
            command.type = "custom"
            command.input = {"command": "\n"}
            with self.assertRaises(ValidationError) as context_manager:
                command.full_clean()
            e = context_manager.exception
            self.assertIn("input", e.message_dict)
            self.assertEqual(e.message_dict["input"], ["'\\n' does not match '.'"])

        with self.subTest("test extra arg on reboot"):
            command.type = "reboot"
            command.input = ["test"]
            with self.assertRaises(ValidationError) as context_manager:
                command.full_clean()
            e = context_manager.exception
            self.assertIn("input", e.message_dict)
            self.assertEqual(
                e.message_dict["input"], ["['test'] is not of type 'null'"]
            )

        with self.subTest("test extra arg on password"):
            command.type = "change_password"
            command.input = {
                "password": "Pass@1234",
                "confirm_password": "Pass@1234",
                "command": "wrong",
            }
            with self.assertRaises(ValidationError) as context_manager:
                command.full_clean()
            e = context_manager.exception
            self.assertIn("input", e.message_dict)
            self.assertIn(
                "Additional properties are not allowed",
                e.message_dict["input"][0],
            )

        with self.subTest("JSON check on arguments"):
            command.type = "change_password"
            command.input = "notjson"
            with self.assertRaises(ValidationError) as context_manager:
                command.full_clean()
            e = context_manager.exception
            self.assertIn("input", e.message_dict)
            self.assertEqual(
                e.message_dict["input"],
                ["'notjson' is not of type 'object'"],
            )

        with self.subTest("JSON check on arguments"):
            command.type = "change_password"
            command.input = []
            with self.assertRaises(ValidationError) as context_manager:
                command.full_clean()
            e = context_manager.exception
            self.assertIn("input", e.message_dict)
            self.assertEqual(e.message_dict["input"], ["[] is not of type 'object'"])

        with self.subTest("Test executing command not available for org"):
            org_id = dc.device.organization_id
            with mock.patch.dict(
                ORGANIZATION_ENABLED_COMMANDS, {str(org_id): ("reboot",)}
            ):
                with self.assertRaises(ValidationError) as context_manager:
                    command.full_clean()
                exception = context_manager.exception
                self.assertIn("input", exception.message_dict)
                self.assertEqual(
                    exception.message_dict["input"],
                    [
                        '"change_password" command is not available'
                        " for this organization"
                    ],
                )

        with self.subTest("Test command creation without device connection"):
            device = dc.device
            device.deviceconnection_set.all().delete()
            with self.assertRaises(ValidationError) as context_manager:
                command.full_clean()
            exception = context_manager.exception
            self.assertIn("device", exception.message_dict)
            self.assertEqual(
                exception.message_dict["device"],
                ["Device has no credentials assigned."],
            )

    def test_command_validation_deactivated_device(self):
        dc = self._create_device_connection()

        with self.subTest("deactivating device does not block command creation"):
            dc.device._is_deactivated = True
            dc.device.save(update_fields=["_is_deactivated"])
            dc.device.config.set_status_deactivating()
            device = Device.objects.get(pk=dc.device.pk)
            command = Command(
                device=device,
                connection=dc,
                type="custom",
                input={"command": "echo test"},
            )
            command.clean()

        with self.subTest("fully deactivated device blocks command creation"):
            dc.device.config.set_status_deactivated()
            device = Device.objects.get(pk=dc.device.pk)
            command = Command(
                device=device,
                connection=dc,
                type="custom",
                input={"command": "echo test"},
            )
            with self.assertRaises(ValidationError) as ctx:
                command.clean()
            self.assertIn("device", ctx.exception.message_dict)
            self.assertEqual(
                ctx.exception.message_dict["device"], ["Device is deactivated."]
            )

    @tag("skip_prod")
    def test_enabled_command(self):
        self.assertEqual(
            ORGANIZATION_ENABLED_COMMANDS["__all__"], tuple(COMMANDS.keys())
        )

    def test_custom_command(self):
        command = Command(input="test", type="change_password")
        with self.assertRaises(TypeError) as context_manager:
            command.custom_command
        self.assertEqual(
            str(context_manager.exception),
            "custom_commands property is not applicable in "
            'command instance of type "change_password"',
        )

    def test_arguments(self):
        command = Command(
            type="change_password",
            input={"password": "newpwd", "confirm_password": "newpwd"},
        )
        self.assertEqual(list(command.arguments), ["newpwd", "newpwd"])

        with self.subTest("value error"):
            command = Command(input=["echo test"], type="custom")
            with self.assertRaises(TypeError) as context_manager:
                command.arguments
            self.assertEqual(
                str(context_manager.exception),
                "arguments property is not applicable in "
                'command instance of type "custom"',
            )

    @mock.patch(_connect_path)
    def test_execute_command_failure_exit_code(self, connect_mocked):
        dc = self._create_device_connection()
        command = Command(
            device=dc.device,
            connection=dc,
            type="custom",
            input={"command": "cat /tmp/doesntexist"},
        )
        command.full_clean()
        stdout = "not found"
        stderr = "error"
        with mock.patch(_exec_command_path) as mocked:
            mocked.return_value = self._exec_command_return_value(
                stdout=stdout, stderr=stderr, exit_code=1
            )
            command.save()
            # must call this explicitly because lack of transactions in this test case
            command.execute()
            connect_mocked.assert_called_once()
            mocked.assert_called_once()
        command.refresh_from_db()
        self.assertEqual(command.status, "failed")
        info = 'Command "cat /tmp/doesntexist" returned non-zero exit code: 1'
        self.assertEqual(command.output, f"{stdout}\n{stderr}\n{info}\n")

    def test_execute_command_failure_connection_failed(self):
        dc = self._create_device_connection()
        command = Command(
            device=dc.device,
            connection=dc,
            type="custom",
            input={"command": "echo test"},
        )
        command.full_clean()
        with mock.patch(_connect_path) as mocked_connect:
            mocked_connect.side_effect = Exception("Authentication failed.")
            command.save()
            # must call this explicitly because lack of transactions in this test case
            command.execute()
            mocked_connect.assert_called_once()
        command.refresh_from_db()
        dc.refresh_from_db()
        self.assertEqual(command.status, "failed")
        self.assertFalse(dc.is_working)
        self.assertEqual(command.output, dc.failure_reason)

        with self.subTest("attempt to repeat execution should fail"):
            with self.assertRaises(RuntimeError) as context_manager:
                command.execute()
            self.assertEqual(
                str(context_manager.exception),
                "This command has already been executed, " "please create a new one.",
            )

    @mock.patch(_connect_path)
    def test_execute_reboot(self, connect_mocked):
        dc = self._create_device_connection()
        command = Command(device=dc.device, connection=dc, type="reboot")
        command.full_clean()
        with mock.patch(_exec_command_path) as mocked_exec_command:
            mocked_exec_command.return_value = self._exec_command_return_value(
                stdout="Rebooting."
            )
            command.save()
            # must call this explicitly because lack of transactions in this test case
            command.execute()
            connect_mocked.assert_called_once()
            mocked_exec_command.assert_called_once()
            mocked_exec_command.assert_called_with(
                "reboot", timeout=app_settings.SSH_COMMAND_TIMEOUT
            )
        command.refresh_from_db()
        self.assertEqual(command.status, "success")
        self.assertEqual(command.output, "Rebooting.\n")

        with self.subTest("attempt to repeat execution should fail"):
            with self.assertRaises(RuntimeError) as context_manager:
                command.execute()
            self.assertEqual(
                str(context_manager.exception),
                "This command has already been executed, " "please create a new one.",
            )

    @mock.patch(_connect_path)
    def test_execute_change_password(self, connect_mocked):
        dc = self._create_device_connection()
        command = Command(
            device=dc.device,
            connection=dc,
            type="change_password",
            input={"password": "Newpasswd@123", "confirm_password": "Newpasswd@123"},
        )
        command.full_clean()
        with mock.patch(_exec_command_path) as mocked_exec_command:
            mocked_exec_command.return_value = self._exec_command_return_value(
                stdout="Changed password for user root."
            )
            command.save()
            # must call this explicitly because lack of transactions in this test case
            command.execute()
            connect_mocked.assert_called_once()
            mocked_exec_command.assert_called_once()
            mocked_exec_command.assert_called_with(
                'echo -e "Newpasswd@123\nNewpasswd@123" | passwd root',
                timeout=app_settings.SSH_COMMAND_TIMEOUT,
            )
        command.refresh_from_db()
        self.assertEqual(command.status, "success")
        self.assertEqual(command.output, "Changed password for user root.\n")
        self.assertEqual(list(command.arguments), ["********"])

    @mock.patch(_connect_path)
    @mock.patch.dict(
        ORGANIZATION_ENABLED_COMMANDS, {"__all__": ("callable_ping", "path_ping")}
    )
    def test_execute_user_registered_command(self, connect_mocked):
        @mock.patch(_exec_command_path)
        def _command_assertions(destination_address, mocked_exec_command):
            command.full_clean()
            mocked_exec_command.return_value = self._exec_command_return_value(
                stdout="Destination host unreachable"
            )
            command.save()
            # must call this explicitly because lack of transactions in this test case
            command.execute()
            connect_mocked.assert_called()
            mocked_exec_command.assert_called_once()
            mocked_exec_command.assert_called_with(
                f"ping -c 4 {destination_address} -I eth0",
                timeout=app_settings.SSH_COMMAND_TIMEOUT,
            )
            command.refresh_from_db()
            self.assertEqual(command.status, "success")
            self.assertEqual(command.output, stderr + "\n")

        ping_command_schema = {
            "label": "Ping",
            "schema": {
                "title": "Ping",
                "type": "object",
                "required": ["destination_address"],
                "properties": {
                    "destination_address": {
                        "type": "string",
                        "title": "Destination Address",
                        "pattern": ".",
                    },
                    "interface_name": {"type": "string", "title": "Interface Name"},
                },
                "message": "Destination Address cannot be empty",
                "additionalProperties": False,
            },
        }
        callable_path = (
            "openwisp_controller.connection.tests.utils." "_ping_command_callable"
        )
        dc = self._create_device_connection()
        stderr = "Destination host unreachable"

        with self.subTest("Callable is a method"):
            ping_command_schema["callable"] = import_string(callable_path)
            register_command("callable_ping", ping_command_schema)
            command = Command(
                device=dc.device,
                connection=dc,
                type="callable_ping",
                input={"destination_address": "example.com", "interface_name": "eth0"},
            )
            _command_assertions("example.com")

        with self.subTest("Callable is dotted path"):
            ping_command_schema["callable"] = callable_path
            register_command("path_ping", ping_command_schema)
            command = Command(
                device=dc.device,
                connection=dc,
                type="path_ping",
                input={
                    "destination_address": "subdomain.example.com",
                    "interface_name": "eth0",
                },
            )
            _command_assertions("subdomain.example.com")

        unregister_command("callable_ping")
        unregister_command("path_ping")

    @mock.patch(_connect_path)
    @mock.patch.dict(COMMANDS, {})
    @mock.patch.dict(ORGANIZATION_ENABLED_COMMANDS, {"__all__": ("restart_network",)})
    @mock.patch(_exec_command_path)
    def test_execute_user_registered_command_without_input(
        self, mocked_exec_command, connect_mocked
    ):
        restart_network_schema = {
            "label": "Restart Network",
            "schema": {
                "title": "Restart Network",
                "type": "null",
                "additionalProperties": False,
            },
            "callable": "openwisp_controller.connection.tests.utils"
            "._restart_network_command_callable",
        }
        dc = self._create_device_connection()
        register_command("restart_network", restart_network_schema)
        command = Command(
            device=dc.device,
            connection=dc,
            type="restart_network",
        )
        command.full_clean()
        mocked_exec_command.return_value = self._exec_command_return_value(
            stdout="Network restarted"
        )
        command.save()
        # must call this explicitly because lack of transactions in this test case
        command.execute()
        connect_mocked.assert_called()
        mocked_exec_command.assert_called_once()
        mocked_exec_command.assert_called_with(
            "/etc/init.d/networking restart",
            timeout=app_settings.SSH_COMMAND_TIMEOUT,
        )
        command.refresh_from_db()
        self.assertEqual(command.status, "success")
        self.assertEqual(command.output, "Network restarted\n")

    def test_command_permissions(self):
        ct = ContentType.objects.get_by_natural_key(
            app_label=self.app_label, model="command"
        )
        operator_group = Group.objects.get(name="Operator")
        admin_group = Group.objects.get(name="Administrator")
        operator_permissions = operator_group.permissions.filter(content_type=ct)
        admin_permissions = admin_group.permissions.filter(content_type=ct)

        with self.subTest("operator permissions"):
            self.assertEqual(operator_permissions.count(), 2)
            self.assertTrue(
                operator_permissions.filter(codename="add_command").exists()
            )
            self.assertTrue(
                operator_permissions.filter(codename="view_command").exists()
            )

        with self.subTest("administrator permissions"):
            self.assertEqual(admin_permissions.count(), 4)

    @mock.patch(_connect_path)
    def test_command_multiple_connections(self, connect_mocked):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)
        dc1 = self._create_device_connection(
            device=device,
            credentials=self._create_credentials(organization=org, name="test1"),
            is_working=True,
        )
        dc2 = self._create_device_connection(
            device=device,
            credentials=self._create_credentials(organization=org, name="test2"),
            is_working=False,
        )

        with self.subTest("Test auto assignment of connection"):
            command = Command(device=device, type="reboot")
            command.full_clean()
            with mock.patch(_exec_command_path) as mocked_exec_command:
                mocked_exec_command.return_value = self._exec_command_return_value(
                    stdout="Rebooting."
                )
                command.save()
                command.execute()
            connect_mocked.assert_called_once()
            command.refresh_from_db()
            self.assertEqual(command.connection, dc1)

        connect_mocked.reset_mock()
        with self.subTest("Test all connection failed"):
            connect_mocked.side_effect = Exception("Authentication failed.")
            command = Command(device=device, type="reboot")
            command.full_clean()
            command.save()
            command.execute()
            self.assertEqual(connect_mocked.call_count, 2)
            command.refresh_from_db()
            self.assertIn(command.connection, [dc1, dc2])

    def test_batch_command_str(self):
        org = self._get_org()
        batch = self._create_batch_command(organization=org)
        self.assertEqual(str(batch), "test-label")

    def test_batch_command_total_devices_successful_failed(self):
        org = self._get_org()
        device1 = self._create_device(organization=org)
        self._create_config(device=device1)
        dc1 = self._create_device_connection(device=device1)
        device2 = self._create_device(
            name="device2",
            mac_address="00:11:22:33:44:02",
            organization=org,
        )
        self._create_config(device=device2)
        dc2 = self._create_device_connection(
            device=device2,
            credentials=self._create_credentials(
                name="Test credentials 2",
                organization=org,
            ),
        )
        batch = self._create_batch_command(organization=org)
        Command.objects.create(
            batch_command=batch,
            device=device1,
            connection=dc1,
            type=batch.type,
            input={"command": "echo test"},
            status="success",
        )
        Command.objects.create(
            batch_command=batch,
            device=device2,
            connection=dc2,
            type=batch.type,
            input={"command": "echo test"},
            status="failed",
        )
        self.assertEqual(batch.total_devices, 2)
        self.assertEqual(batch.successful, 1)
        self.assertEqual(batch.failed, 1)
        self.assertEqual(
            batch.batch_commands.filter(status="success").first().device, device1
        )
        self.assertEqual(
            batch.batch_commands.filter(status="failed").first().device, device2
        )
        self.assertFalse(
            batch.batch_commands.filter(status="success", device=device2).exists()
        )
        self.assertFalse(
            batch.batch_commands.filter(status="failed", device=device1).exists()
        )

    def test_batch_command_skipped_devices(self):
        org = self._get_org()
        batch = self._create_batch_command(organization=org)
        skipped = {
            str(uuid4()): {"name": f"device{index}", "error": f"error {index}"}
            for index in range(3)
        }
        pks = list(skipped)
        batch.skipped_devices = skipped
        batch.save(update_fields=["skipped_devices"])

        with self.subTest("skipped row"):
            row = BatchCommand.build_skipped_row(pks[0], skipped[pks[0]])
            self.assertEqual(
                row,
                {
                    "device": pks[0],
                    "device_name": "device0",
                    "status": "skipped",
                    "status_display": "skipped",
                    "output": "error 0",
                    "modified": None,
                    "is_skipped": True,
                },
            )

        with self.subTest("all rows"):
            rows = batch.get_skipped_rows()
            self.assertEqual([row["device"] for row in rows], pks)

        with self.subTest("sliced rows"):
            self.assertEqual(
                [row["device"] for row in batch.get_skipped_rows(end=2)], pks[:2]
            )
            self.assertEqual(
                [row["device"] for row in batch.get_skipped_rows(start=1, end=3)],
                pks[1:3],
            )

        with self.subTest("count and device ids"):
            self.assertEqual(batch.skipped_count, 3)
            self.assertEqual(list(batch.skipped_device_ids), pks)

        with self.subTest("items are not copied when nothing is filtered"):
            self.assertEqual(batch.get_skipped_items(), skipped.items())

        with self.subTest("items filtered by name"):
            self.assertEqual(
                [pk for pk, _skipped in batch.get_skipped_items(query="DEVICE1")],
                pks[1:2],
            )

        with self.subTest("items filtered by device id"):
            self.assertEqual(
                [pk for pk, _skipped in batch.get_skipped_items(device_ids={pks[2]})],
                pks[2:],
            )

        with self.subTest("preview within the limit"):
            self.assertEqual(
                [row["device"] for row in batch.get_skipped_preview()], pks
            )

        with self.subTest("preview above the limit"):
            skipped = {
                str(uuid4()): {"name": f"device{index}", "error": f"error {index}"}
                for index in range(11)
            }
            pks = list(skipped)
            batch.skipped_devices = skipped
            batch.save(update_fields=["skipped_devices"])
            self.assertEqual(
                [row["device"] for row in batch.get_skipped_preview()],
                pks[:2] + pks[-1:],
            )

        with self.subTest("counts include skipped devices"):
            device = self._create_device(organization=org)
            self._create_config(device=device)
            dc = self._create_device_connection(device=device)
            Command.objects.create(
                batch_command=batch,
                device=device,
                connection=dc,
                type=batch.type,
                input={"command": "echo test"},
                status="success",
            )
            self.assertEqual(batch.affected_devices, 1)
            self.assertEqual(batch.total_devices, 12)

    def test_batch_command_clean_validation(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        device_org2 = self._create_device(organization=org2)

        with self.subTest("devices from different org"):
            batch = self._create_batch_command(organization=org)
            batch.devices.add(device_org2)
            with self.assertRaises(ValidationError) as ctx:
                batch.clean()
            self.assertIn("devices", ctx.exception.message_dict)
            self.assertIn(
                "must belong to the same organization",
                ctx.exception.message_dict["devices"][0],
            )

        with self.subTest("invalid command type for org"):
            with mock.patch.dict(
                ORGANIZATION_ENABLED_COMMANDS,
                {str(org.pk): ("reboot",)},
            ):
                batch = BatchCommand(
                    organization=org,
                    type="custom",
                    input={"command": "echo test"},
                    label="test-label",
                )
                with self.assertRaises(ValidationError) as ctx:
                    batch.clean()
                self.assertIn("type", ctx.exception.message_dict)
                self.assertIn(
                    "not available for the target organization(s)",
                    ctx.exception.message_dict["type"][0],
                )

        with self.subTest("no command enabled for the organization"):
            with mock.patch.dict(
                ORGANIZATION_ENABLED_COMMANDS,
                {str(uuid4()): ("reboot",)},
                clear=True,
            ):
                batch = BatchCommand(
                    organization=org,
                    type="reboot",
                    input=None,
                    label="test-label",
                )
                with self.assertRaises(ValidationError) as ctx:
                    batch.clean()
                self.assertIn("type", ctx.exception.message_dict)
                self.assertIn(
                    "not available for the target organization(s)",
                    ctx.exception.message_dict["type"][0],
                )

        with self.subTest("no command enabled system wide"):
            with mock.patch.dict(
                ORGANIZATION_ENABLED_COMMANDS,
                {str(uuid4()): ("reboot",)},
                clear=True,
            ):
                batch = BatchCommand(type="reboot", input=None, label="test-label")
                with self.assertRaises(ValidationError) as ctx:
                    batch.clean()
                self.assertIn("type", ctx.exception.message_dict)
                self.assertIn(
                    "not available for the target organization(s)",
                    ctx.exception.message_dict["type"][0],
                )

        with self.subTest("invalid JSON schema"):
            batch = BatchCommand(
                organization=org,
                type="change_password",
                input="not_an_object",
                label="test-label",
            )
            with self.assertRaises(ValidationError) as ctx:
                batch.clean()
            self.assertIn("input", ctx.exception.message_dict)

        with self.subTest("group org mismatch"):
            group = DeviceGroup.objects.create(name="test-group", organization=org2)
            batch = BatchCommand(
                organization=org,
                type="custom",
                input={"command": "echo test"},
                label="test-label",
                group=group,
            )
            with self.assertRaises(ValidationError) as ctx:
                batch.clean()
            self.assertIn("group", ctx.exception.message_dict)
            self.assertIn(
                "Please ensure that the organization of this Mass command "
                "and the organization of the related Device Group match",
                ctx.exception.message_dict["group"][0],
            )

        with self.subTest("location org mismatch"):
            location = Location.objects.create(
                name="test-location",
                type="indoor",
                organization=org2,
            )
            batch = BatchCommand(
                organization=org,
                type="custom",
                input={"command": "echo test"},
                label="test-label",
                location=location,
            )
            with self.assertRaises(ValidationError) as ctx:
                batch.clean()
            self.assertIn("location", ctx.exception.message_dict)
            self.assertIn(
                "Please ensure that the organization of this Mass command "
                "and the organization of the related location match",
                ctx.exception.message_dict["location"][0],
            )

    def test_batch_command_create_commands_deactivated_device(self):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)
        self._create_device_connection(device=device)

        with self.subTest("deactivating device does not block create_commands"):
            device._is_deactivated = True
            device.save(update_fields=["_is_deactivated"])
            device.config.set_status_deactivating()
            device = Device.objects.get(pk=device.pk)
            batch = self._create_batch_command(organization=org)
            batch.devices.add(device)
            batch.create_commands()
            self.assertEqual(batch.batch_commands.count(), 1)
            self.assertEqual(batch.skipped_devices, {})

        with self.subTest("fully deactivated device skipped in create_commands"):
            device.config.set_status_deactivated()
            device = Device.objects.get(pk=device.pk)
            batch = self._create_batch_command(organization=org)
            batch.devices.add(device)
            with self.assertLogs(LOGGER_NAME, level="WARNING") as logs:
                batch.create_commands()
            self.assertIn("Skipping device", logs.output[0])
            self.assertEqual(batch.batch_commands.count(), 0)
            self.assertIn(str(device.pk), batch.skipped_devices)
            self.assertIn(
                "Device is deactivated",
                batch.skipped_devices[str(device.pk)]["error"],
            )

    def test_batch_command_create_commands_no_credentials(self):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)
        batch = self._create_batch_command(
            organization=org,
            devices=[device],
        )
        with self.assertLogs(LOGGER_NAME, level="WARNING") as logs:
            batch.create_commands()
        self.assertIn("Skipping device", logs.output[0])
        batch.refresh_from_db()
        self.assertIn(str(device.pk), batch.skipped_devices)
        self.assertIn(
            "Device has no credentials assigned",
            batch.skipped_devices[str(device.pk)]["error"],
        )

    def test_batch_command_create_commands_skip_scenarios(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")

        with self.subTest("org command not allowed"):
            device_a = self._create_device(
                name="device-a",
                mac_address="00:11:22:33:44:aa",
                organization=org,
            )
            self._create_config(device=device_a)
            self._create_device_connection(device=device_a)
            device_b = self._create_device(
                name="device-b",
                mac_address="00:11:22:33:44:bb",
                organization=org2,
            )
            self._create_config(device=device_b)
            self._create_device_connection(device=device_b)
            with mock.patch.dict(
                ORGANIZATION_ENABLED_COMMANDS,
                {str(org2.pk): ("reboot",)},
            ):
                batch = self._create_batch_command(
                    organization=org,
                    devices=[device_a, device_b],
                )
                with self.assertLogs(LOGGER_NAME, level="WARNING") as logs:
                    batch.create_commands()
                self.assertIn("Skipping device", logs.output[0])
                batch.refresh_from_db()
                self.assertIn(str(device_b.pk), batch.skipped_devices)
                self.assertIn(
                    "no longer belongs to the organization",
                    batch.skipped_devices[str(device_b.pk)]["error"],
                )
                db_batch = BatchCommand.objects.get(pk=batch.pk)
                self.assertEqual(batch.skipped_devices, db_batch.skipped_devices)
                command_qs = Command.objects.filter(batch_command=batch)
                self.assertTrue(command_qs.filter(device=device_a).exists())
                self.assertFalse(command_qs.filter(device=device_b).exists())

        with self.subTest("org command not allowed on a system wide batch"):
            with mock.patch.dict(
                ORGANIZATION_ENABLED_COMMANDS,
                {"__all__": ("custom",), str(org2.pk): ("reboot",)},
            ):
                batch = self._create_batch_command(
                    organization=None,
                    devices=[device_b],
                )
                with self.assertLogs(LOGGER_NAME, level="WARNING") as logs:
                    batch.create_commands()
                self.assertIn("Skipping device", logs.output[0])
                batch.refresh_from_db()
                self.assertIn(
                    '"custom" command is not available for this organization',
                    batch.skipped_devices[str(device_b.pk)]["error"],
                )
                self.assertFalse(Command.objects.filter(batch_command=batch).exists())

        with self.subTest("mixed skip scenario"):
            device_ok = self._create_device(
                name="device-ok",
                mac_address="00:11:22:33:44:01",
                organization=org,
            )
            self._create_config(device=device_ok)
            ok_cred = self._create_credentials(name="device-ok-cred", organization=org)
            self._create_device_connection(device=device_ok, credentials=ok_cred)
            device_no_creds = self._create_device(
                name="device-no-creds",
                mac_address="00:11:22:33:44:02",
                organization=org,
            )
            self._create_config(device=device_no_creds)
            device_deactivated = self._create_device(
                name="device-deactivated",
                mac_address="00:11:22:33:44:03",
                organization=org,
            )
            self._create_config(device=device_deactivated)
            dd_cred = self._create_credentials(name="device-dd-cred", organization=org)
            self._create_device_connection(
                device=device_deactivated, credentials=dd_cred
            )
            device_deactivated.deactivate()
            batch = self._create_batch_command(
                organization=org,
                devices=[device_ok, device_no_creds, device_deactivated],
            )
            with self.assertLogs(LOGGER_NAME, level="WARNING") as logs:
                batch.create_commands()
            self.assertEqual(len(logs.output), 2)
            batch.refresh_from_db()
            command_qs = Command.objects.filter(batch_command=batch)
            self.assertEqual(command_qs.count(), 1)
            self.assertTrue(command_qs.filter(device=device_ok).exists())
            self.assertIn(str(device_no_creds.pk), batch.skipped_devices)
            self.assertEqual(
                batch.skipped_devices[str(device_no_creds.pk)]["name"],
                device_no_creds.name,
            )
            self.assertIn(
                "Device has no credentials assigned",
                batch.skipped_devices[str(device_no_creds.pk)]["error"],
            )
            self.assertIn(str(device_deactivated.pk), batch.skipped_devices)
            self.assertIn(
                "Device is deactivated",
                batch.skipped_devices[str(device_deactivated.pk)]["error"],
            )
            self.assertNotIn(str(device_ok.pk), batch.skipped_devices)
            db_batch = BatchCommand.objects.get(pk=batch.pk)
            self.assertEqual(batch.skipped_devices, db_batch.skipped_devices)

    def test_batch_command_create_commands_without_explicit_devices(self):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)
        self._create_device_connection(device=device)
        batch = self._create_batch_command(organization=org)
        batch.create_commands()
        batch.refresh_from_db()
        self.assertEqual(
            [command.device for command in batch.batch_commands.all()], [device]
        )
        self.assertEqual(list(batch.devices.all()), [device])

    def test_batch_command_resolve_devices(self):
        org = self._get_org()
        device1 = self._create_device(
            name="device1",
            mac_address="00:11:22:33:44:01",
            organization=org,
        )
        device2 = self._create_device(
            name="device2",
            mac_address="00:11:22:33:44:02",
            organization=org,
        )

        with self.subTest("explicit devices via M2M"):
            batch = self._create_batch_command(
                organization=org,
                devices=[device1],
            )
            resolved = list(batch.resolve_devices())
            self.assertEqual(resolved, [device1])

        with self.subTest("organization-scoped (no explicit devices)"):
            batch = self._create_batch_command(organization=org)
            resolved = list(batch.resolve_devices())
            self.assertIn(device1, resolved)
            self.assertIn(device2, resolved)

        with self.subTest("group filtering"):
            group = DeviceGroup.objects.create(name="test-group", organization=org)
            device1.group = group
            device1.save()
            batch = self._create_batch_command(organization=org, group=group)
            resolved = list(batch.resolve_devices())
            self.assertIn(device1, resolved)
            self.assertNotIn(device2, resolved)

        with self.subTest("location filtering"):
            location = Location.objects.create(
                name="test-location",
                type="indoor",
                organization=org,
            )
            DeviceLocation.objects.create(content_object=device2, location=location)
            batch = self._create_batch_command(organization=org, location=location)
            resolved = list(batch.resolve_devices())
            self.assertIn(device2, resolved)
            self.assertNotIn(device1, resolved)

        with self.subTest("group and location combined"):
            DeviceLocation.objects.create(content_object=device1, location=location)
            batch = self._create_batch_command(
                organization=org,
                group=device1.group,
                location=location,
            )
            resolved = list(batch.resolve_devices())
            self.assertIn(device1, resolved)
            self.assertNotIn(device2, resolved)

        with self.subTest("no devices match"):
            empty_group = DeviceGroup.objects.create(
                name="empty-group",
                organization=org,
            )
            batch = self._create_batch_command(
                organization=org,
                group=empty_group,
            )
            resolved = list(batch.resolve_devices())
            self.assertEqual(resolved, [])

    def test_batch_command_dry_run_method(self):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)

        with self.subTest("dry_run with type"):
            result = BatchCommand.dry_run(
                organization=org,
                type="custom",
                input={"command": "echo test"},
            )
            self.assertIn("devices", result)
            self.assertIn(device, result["devices"])

        with self.subTest("dry_run without type"):
            result = BatchCommand.dry_run(organization=org)
            self.assertIn("devices", result)
            self.assertIn(device, result["devices"])

        with self.subTest("dry_run with explicit devices"):
            result = BatchCommand.dry_run(
                organization=org,
                devices=[device],
            )
            self.assertEqual(result["devices"], [device])

        with self.subTest("dry_run with group"):
            group = DeviceGroup.objects.create(name="dry-run-group", organization=org)
            device.group = group
            device.save()
            result = BatchCommand.dry_run(
                organization=org,
                type="custom",
                input={"command": "echo test"},
                group=group,
            )
            self.assertIn("devices", result)
            self.assertIn(device, result["devices"])

        with self.subTest("dry_run with location"):
            location = Location.objects.create(
                name="dry-run-loc",
                type="indoor",
                organization=org,
            )
            DeviceLocation.objects.create(content_object=device, location=location)
            result = BatchCommand.dry_run(
                organization=org,
                type="custom",
                input={"command": "echo test"},
                location=location,
            )
            self.assertIn("devices", result)
            self.assertIn(device, result["devices"])

        with self.subTest("dry_run with group and location"):
            result = BatchCommand.dry_run(
                organization=org,
                type="custom",
                input={"command": "echo test"},
                group=group,
                location=location,
            )
            self.assertIn("devices", result)
            self.assertIn(device, result["devices"])

        with self.subTest("dry run org-wide"):
            device2 = self._create_device(
                name="dry-org-dev2",
                mac_address="00:11:22:33:44:77",
                organization=org,
            )
            result = BatchCommand.dry_run(organization=org)
            self.assertIn("devices", result)
            self.assertIn(device, result["devices"])
            self.assertIn(device2, result["devices"])

    def test_batch_command_execute_method(self):
        org = self._get_org()
        empty_org = self._create_org(name="empty-org", slug="empty-org")

        with self.subTest("execute with no devices"):
            with self.assertRaises(ValidationError) as ctx:
                BatchCommand.execute(
                    organization=empty_org,
                    type="custom",
                    input={"command": "echo test"},
                    label="test-label",
                )
            self.assertIn(
                "No devices match",
                str(ctx.exception),
            )

        cred = self._create_credentials(
            name="exec-cred",
            organization=org,
        )
        device1 = self._create_device(
            name="exec-dev1",
            mac_address="00:11:22:33:44:e1",
            organization=org,
        )
        self._create_config(device=device1)
        self._create_device_connection(device=device1, credentials=cred)
        device2 = self._create_device(
            name="exec-dev2",
            mac_address="00:11:22:33:44:e2",
            organization=org,
        )
        self._create_config(device=device2)
        self._create_device_connection(device=device2, credentials=cred)
        group = DeviceGroup.objects.create(name="exec-group", organization=org)
        device1.group = group
        device1.save()
        location = Location.objects.create(
            name="exec-loc",
            type="indoor",
            organization=org,
        )
        DeviceLocation.objects.create(content_object=device2, location=location)

        with self.subTest("execute with explicit devices"):
            batch = BatchCommand.execute(
                organization=org,
                type="custom",
                input={"command": "echo test"},
                label="test-label",
                devices=[device1],
            )
            batch.create_commands()
            self.assertEqual(batch.batch_commands.count(), 1)
            self.assertEqual(batch.batch_commands.first().device, device1)

        with self.subTest("execute with group"):
            batch = BatchCommand.execute(
                organization=org,
                type="custom",
                input={"command": "echo test"},
                label="test-label",
                group=group,
            )
            batch.create_commands()
            self.assertEqual(batch.batch_commands.count(), 1)
            self.assertEqual(batch.batch_commands.first().device, device1)

        with self.subTest("execute with location"):
            batch = BatchCommand.execute(
                organization=org,
                type="custom",
                input={"command": "echo test"},
                label="test-label",
                location=location,
            )
            batch.create_commands()
            self.assertEqual(batch.batch_commands.count(), 1)
            self.assertEqual(batch.batch_commands.first().device, device2)

        with self.subTest("execute with group and location"):
            DeviceLocation.objects.create(content_object=device1, location=location)
            batch = BatchCommand.execute(
                organization=org,
                type="custom",
                input={"command": "echo test"},
                label="test-label",
                group=group,
                location=location,
            )
            batch.create_commands()
            self.assertEqual(batch.batch_commands.count(), 1)
            self.assertEqual(batch.batch_commands.first().device, device1)

        with self.subTest("execute org-wide"):
            batch = BatchCommand.execute(
                organization=org,
                type="custom",
                input={"command": "echo test"},
                label="test-label",
            )
            batch.create_commands()
            self.assertEqual(batch.batch_commands.count(), 2)
            cmd_devices = [c.device for c in batch.batch_commands.all()]
            self.assertIn(device1, cmd_devices)
            self.assertIn(device2, cmd_devices)

    def test_batch_command_execute_org_mismatch(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        device_org2 = self._create_device(
            name="exec-mm-dev",
            mac_address="00:11:22:33:44:99",
            organization=org2,
        )
        self._create_config(device=device_org2)
        self._create_device_connection(device=device_org2)

        with self.subTest("device org mismatch"):
            with self.assertRaises(ValidationError) as ctx:
                BatchCommand.execute(
                    organization=org,
                    type="custom",
                    input={"command": "echo test"},
                    label="test-label",
                    devices=[device_org2],
                )
            self.assertIn("devices", ctx.exception.message_dict)
            self.assertIn(
                "must belong to the same organization",
                ctx.exception.message_dict["devices"][0],
            )

        with self.subTest("devices of different organizations without organization"):
            device_org1 = self._create_device(
                name="exec-mm-dev-org1",
                mac_address="00:11:22:33:44:97",
            )
            with self.assertRaises(ValidationError) as ctx:
                BatchCommand.execute(
                    type="custom",
                    input={"command": "echo test"},
                    label="test-label",
                    devices=[device_org1, device_org2],
                )
            self.assertIn("devices", ctx.exception.message_dict)
            self.assertIn(
                "must belong to the same organization",
                ctx.exception.message_dict["devices"][0],
            )

        with self.subTest("a system wide batch accepts devices of different orgs"):
            batch = BatchCommand.execute(
                type="custom",
                input={"command": "echo test"},
                label="test-label",
                devices=[device_org1, device_org2],
                system_wide=True,
            )
            self.assertIsNone(batch.organization_id)
            self.assertEqual(set(batch.devices.all()), {device_org1, device_org2})

        with self.subTest("group org mismatch"):
            group_org2 = DeviceGroup.objects.create(
                name="exec-mm-group",
                organization=org2,
            )
            with self.assertRaises(ValidationError) as ctx:
                BatchCommand.execute(
                    organization=org,
                    type="custom",
                    input={"command": "echo test"},
                    label="test-label",
                    group=group_org2,
                )
            self.assertIn("group", ctx.exception.message_dict)
            self.assertIn(
                "Please ensure that the organization of this Mass command "
                "and the organization of the related Device Group match",
                ctx.exception.message_dict["group"][0],
            )

        with self.subTest("location org mismatch"):
            location_org2 = Location.objects.create(
                name="exec-mm-loc",
                type="indoor",
                organization=org2,
            )
            with self.assertRaises(ValidationError) as ctx:
                BatchCommand.execute(
                    organization=org,
                    type="custom",
                    input={"command": "echo test"},
                    label="test-label",
                    location=location_org2,
                )
            self.assertIn("location", ctx.exception.message_dict)
            self.assertIn(
                "Please ensure that the organization of this Mass command "
                "and the organization of the related location match",
                ctx.exception.message_dict["location"][0],
            )

    def test_batch_command_dry_run_org_mismatch(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        device_org2 = self._create_device(
            name="dry-mm-dev",
            mac_address="00:11:22:33:44:98",
            organization=org2,
        )

        with self.subTest("device org mismatch"):
            with self.assertRaises(ValidationError) as ctx:
                BatchCommand.dry_run(
                    organization=org,
                    devices=[device_org2],
                )
            self.assertIn("devices", ctx.exception.message_dict)
            self.assertIn(
                "must belong to the same organization",
                ctx.exception.message_dict["devices"][0],
            )

        with self.subTest("devices of different organizations without organization"):
            device_org1 = self._create_device(
                name="dry-mm-dev-org1",
                mac_address="00:11:22:33:44:97",
            )
            with self.assertRaises(ValidationError) as ctx:
                BatchCommand.dry_run(devices=[device_org1, device_org2])
            self.assertIn("devices", ctx.exception.message_dict)
            self.assertIn(
                "must belong to the same organization",
                ctx.exception.message_dict["devices"][0],
            )

        with self.subTest("group org mismatch"):
            group_org2 = DeviceGroup.objects.create(
                name="dry-mm-group",
                organization=org2,
            )
            with self.assertRaises(ValidationError) as ctx:
                BatchCommand.dry_run(
                    organization=org,
                    type="custom",
                    input={"command": "echo test"},
                    group=group_org2,
                )
            self.assertIn("group", ctx.exception.message_dict)
            self.assertIn(
                "Please ensure that the organization of this Mass command "
                "and the organization of the related Device Group match",
                ctx.exception.message_dict["group"][0],
            )

        with self.subTest("location org mismatch"):
            location_org2 = Location.objects.create(
                name="dry-mm-loc",
                type="indoor",
                organization=org2,
            )
            with self.assertRaises(ValidationError) as ctx:
                BatchCommand.dry_run(
                    organization=org,
                    type="custom",
                    input={"command": "echo test"},
                    location=location_org2,
                )
            self.assertIn("location", ctx.exception.message_dict)
            self.assertIn(
                "Please ensure that the organization of this Mass command "
                "and the organization of the related location match",
                ctx.exception.message_dict["location"][0],
            )

    def test_batch_command_create_commands_idempotent(self):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)
        self._create_device_connection(device=device)
        batch = self._create_batch_command(
            organization=org,
            devices=[device],
        )
        batch.create_commands()
        self.assertEqual(Command.objects.filter(batch_command=batch).count(), 1)
        batch.create_commands()
        self.assertEqual(
            Command.objects.filter(batch_command=batch).count(),
            1,
            "create_commands must be idempotent",
        )

    def test_batch_command_calculate_and_update_status(self):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)
        dc = self._create_device_connection(device=device)
        batch = self._create_batch_command(organization=org)

        with self.subTest("no commands shows idle"):
            batch.status = "in-progress"
            batch.save(update_fields=["status"])
            batch.calculate_and_update_status()
            batch.refresh_from_db()
            self.assertEqual(batch.status, "idle")

        with self.subTest("all in-progress shows in-progress"):
            Command.objects.create(
                batch_command=batch,
                device=device,
                connection=dc,
                type=batch.type,
                input={"command": "echo test"},
                status="in-progress",
            )
            batch.calculate_and_update_status()
            batch.refresh_from_db()
            self.assertEqual(batch.status, "in-progress")

        with self.subTest("some failed shows failed"):
            Command.objects.filter(batch_command=batch).update(status="success")
            device2 = self._create_device(
                name="device2",
                mac_address="00:11:22:33:44:02",
                organization=org,
            )
            self._create_config(device=device2)
            dc2 = self._create_device_connection(
                device=device2,
                credentials=self._create_credentials(
                    name="Test credentials 2",
                    organization=org,
                ),
            )
            Command.objects.create(
                batch_command=batch,
                device=device2,
                connection=dc2,
                type=batch.type,
                input={"command": "echo test"},
                status="failed",
            )
            batch.calculate_and_update_status()
            batch.refresh_from_db()
            self.assertEqual(batch.status, "failed")

        with self.subTest("all success shows success"):
            batch2 = self._create_batch_command(organization=org)
            Command.objects.create(
                batch_command=batch2,
                device=device,
                connection=dc,
                type=batch2.type,
                input={"command": "echo test"},
                status="success",
            )
            batch2.calculate_and_update_status()
            batch2.refresh_from_db()
            self.assertEqual(batch2.status, "success")

        with self.subTest("all success with skipped shows failed"):
            batch3 = self._create_batch_command(organization=org)
            batch3.skipped_devices = {
                str(device.pk): {"name": device.name, "error": "no credentials"}
            }
            batch3.save(update_fields=["skipped_devices"])
            Command.objects.create(
                batch_command=batch3,
                device=device,
                connection=dc,
                type=batch3.type,
                input={"command": "echo test"},
                status="success",
            )
            batch3.calculate_and_update_status()
            batch3.refresh_from_db()
            self.assertEqual(batch3.status, "failed")

        with self.subTest("no change shows no extra save"):
            initial_modified = batch2.modified
            batch2.calculate_and_update_status()
            batch2.refresh_from_db()
            self.assertEqual(batch2.modified, initial_modified)

    def test_batch_command_status_rejects_a_stale_calculation(self):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)
        dc = self._create_device_connection(device=device)
        batch = self._create_batch_command(organization=org)
        Command.objects.create(
            batch_command=batch,
            device=device,
            connection=dc,
            type=batch.type,
            input={"command": "echo test"},
            status="success",
        )
        BatchCommand.objects.filter(pk=batch.pk).update(status="in-progress")
        batch.refresh_from_db()
        original = BatchCommand._compute_status
        calls = []

        def compute(self):
            calls.append(self.status)
            if len(calls) == 1:
                BatchCommand.objects.filter(pk=batch.pk).update(
                    status="failed",
                    skipped_devices={
                        str(uuid4()): {"name": "device1", "error": "no credentials"}
                    },
                )
                return "success"
            return original(self)

        with mock.patch.object(BatchCommand, "_compute_status", compute):
            batch.calculate_and_update_status()
        batch.refresh_from_db()
        self.assertEqual(len(calls), 1)
        self.assertEqual(batch.status, "failed")

    def test_batch_command_status_is_written_once(self):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)
        dc = self._create_device_connection(device=device)
        batch = self._create_batch_command(organization=org)
        with mock.patch.object(Command, "_schedule_command"):
            Command.objects.create(
                batch_command=batch,
                device=device,
                connection=dc,
                type=batch.type,
                input={"command": "echo test"},
                status="success",
            )
        BatchCommand.objects.filter(pk=batch.pk).update(status="in-progress")
        batch.refresh_from_db()
        modified = batch.modified

        with mock.patch.object(BatchCommand, "save") as save:
            with mock.patch.object(handlers, "send_batch_update") as publish:
                batch.calculate_and_update_status()
        save.assert_not_called()
        publish.assert_called_once()
        group, payload = publish.call_args[0]
        self.assertEqual(group, f"config.batchcommand-{batch.pk}")
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["type"], "batch_status")
        batch.refresh_from_db()
        self.assertEqual(batch.status, "success")
        self.assertGreater(batch.modified, modified)

    def test_batch_command_device_transferred_to_another_org(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        device = self._create_device(organization=org)
        self._create_config(device=device)
        dc = self._create_device_connection(device=device)
        batch = self._create_batch_command(organization=org)
        batch.devices.set([device])

        with self.subTest("the transferred device is skipped at creation"):
            device.organization = org2
            device.save(update_fields=["organization"])
            with mock.patch.object(Command, "_schedule_command"):
                with self.assertLogs(LOGGER_NAME, level="WARNING") as logs:
                    batch.create_commands()
            batch.refresh_from_db()
            self.assertIn("Skipping device", logs.output[0])
            self.assertIn(str(device.pk), batch.skipped_devices)
            self.assertIn(
                "no longer belongs to the organization",
                batch.skipped_devices[str(device.pk)]["error"],
            )
            self.assertFalse(batch.batch_commands.exists())

        with self.subTest("a command of a transferred device is not executed"):
            device.organization = org
            device.save(update_fields=["organization"])
            with mock.patch.object(Command, "_schedule_command"):
                command = Command.objects.create(
                    batch_command=batch,
                    device=device,
                    connection=dc,
                    type=batch.type,
                    input={"command": "echo test"},
                )
            device.organization = org2
            device.save(update_fields=["organization"])
            with mock.patch.object(Command, "_exec_command") as exec_command:
                with self.assertLogs(LOGGER_NAME, level="WARNING") as logs:
                    command.execute()
            exec_command.assert_not_called()
            self.assertIn(
                f"Not executing command {command.pk} of batch {batch.pk}",
                logs.output[0],
            )
            self.assertIn(str(org2.pk), logs.output[0])
            command.refresh_from_db()
            self.assertEqual(command.status, "failed")
            self.assertIn("no longer belongs to the organization", command.output)

    def test_batch_command_permissions(self):
        ct = ContentType.objects.get_by_natural_key(
            app_label=self.app_label, model="batchcommand"
        )
        operator_group = Group.objects.get(name="Operator")
        admin_group = Group.objects.get(name="Administrator")
        operator_permissions = operator_group.permissions.filter(content_type=ct)
        admin_permissions = admin_group.permissions.filter(content_type=ct)

        with self.subTest("operator permissions"):
            self.assertEqual(operator_permissions.count(), 2)
            self.assertTrue(
                operator_permissions.filter(codename="add_batchcommand").exists()
            )
            self.assertTrue(
                operator_permissions.filter(codename="view_batchcommand").exists()
            )

        with self.subTest("administrator permissions"):
            self.assertEqual(admin_permissions.count(), 4)


class TestModelsTransaction(BaseTestModels, TransactionTestCase):
    def _prepare_conf_object(self, organization=None):
        if not organization:
            organization = self._create_org(name="org1")
        cred = self._create_credentials_with_key(
            organization=organization, port=self.ssh_server.port
        )
        device = self._create_device(organization=organization)
        update_strategy = app_settings.UPDATE_STRATEGIES[0][0]
        conf = self._create_config(device=device, status="applied")
        self._create_device_connection(
            device=device, credentials=cred, update_strategy=update_strategy
        )
        conf.config = {
            "interfaces": [
                {
                    "name": "eth10",
                    "type": "ethernet",
                    "addresses": [{"family": "ipv4", "proto": "dhcp"}],
                }
            ]
        }
        conf.full_clean()
        return conf

    @capture_any_output()
    @mock.patch(_connect_path)
    @mock.patch("time.sleep")
    def test_device_config_created(self, mocked_sleep, mocked_connect):
        """
        The update_config task must not be initiated when
        the device has just been created
        """
        test_org = self._get_org()
        self._create_credentials(auto_add=True, organization=test_org)
        self._create_template(default=True, organization=test_org)
        self._prepare_conf_object(organization=test_org)
        mocked_connect.assert_not_called()

    @capture_any_output()
    @mock.patch(_connect_path)
    @mock.patch("time.sleep")
    def test_device_config_update(self, mocked_sleep, mocked_connect):
        def _assert_version_check_command(mocked_exec):
            args, _ = mocked_exec.call_args_list[0]
            self.assertEqual(
                args[0],
                "(openwisp-config --version || openwisp_config --version) 2>/dev/null",
            )

        def _assert_applying_conf_test_command(mocked_exec):
            args, _ = mocked_exec_command.call_args_list[1]
            self.assertEqual(
                args[0],
                "test -f /tmp/openwisp/applying_conf",
            )

        conf = self._prepare_conf_object()

        with self.subTest("Unable to get openwisp-config version"):
            with mock.patch(_exec_command_path) as mocked_exec_command:
                mocked_exec_command.return_value = self._exec_command_return_value(
                    exit_code=1
                )
                conf.save()
                self.assertEqual(mocked_exec_command.call_count, 1)
                _assert_version_check_command(mocked_exec_command)
            conf.refresh_from_db()
            self.assertEqual(conf.status, "modified")

        with self.subTest("openwisp_config >= 0.6.0a"):
            conf.config = {"dns_servers": []}
            conf.full_clean()
            with mock.patch(_exec_command_path) as mocked_exec_command:
                mocked_exec_command.return_value = self._exec_command_return_value(
                    stdout="openwisp_config 0.6.0a"
                )
                conf.save()
                self.assertEqual(mocked_exec_command.call_count, 2)
                _assert_version_check_command(mocked_exec_command)
                args, _ = mocked_exec_command.call_args_list[1]
                self.assertIn("OW_CONFIG_PID", args[0])
            conf.refresh_from_db()
            self.assertEqual(conf.status, "modified")

        with self.subTest("openwisp_config < 0.6.0a: exit_code 0"):
            conf.config = {"interfaces": [{"name": "eth00", "type": "ethernet"}]}
            conf.full_clean()
            with mock.patch(_exec_command_path) as mocked_exec_command:
                mocked_exec_command.return_value = self._exec_command_return_value(
                    stdout="openwisp_config 0.5.0"
                )
                conf.save()
                self.assertEqual(mocked_exec_command.call_count, 2)
                _assert_version_check_command(mocked_exec_command)
                _assert_applying_conf_test_command(mocked_exec_command)
            conf.refresh_from_db()
            self.assertEqual(conf.status, "modified")

        with self.subTest("openwisp_config < 0.6.0a: exit_code 1"):
            conf.config = {"radios": []}
            conf.full_clean()
            with mock.patch(_exec_command_path) as mocked_exec_command:
                stdin, stdout, stderr = self._exec_command_return_value(
                    stdout="openwisp_config 0.5.0"
                )
                # An iterable side effect is required for different exit codes:
                # 1. Checking openwisp_config returns with 0
                # 2. Testing presence of /tmp/openwisp/applying_conf returns with 1
                # 3. Restarting openwisp_config returns with 0 exit code
                type(stdout.channel).exit_status = PropertyMock(side_effect=[0, 1, 1])
                mocked_exec_command.return_value = (stdin, stdout, stderr)
                conf.save()
                self.assertEqual(mocked_exec_command.call_count, 3)
                _assert_version_check_command(mocked_exec_command)
                _assert_applying_conf_test_command(mocked_exec_command)
                args, _ = mocked_exec_command.call_args_list[2]
                self.assertEqual(args[0], "/etc/init.d/openwisp_config restart")
            conf.refresh_from_db()
            # exit code 1 considers the update not successful
            self.assertEqual(conf.status, "modified")

    @mock.patch("time.sleep")
    @mock.patch.object(DeviceConnection, "update_config")
    @mock.patch.object(DeviceConnection, "get_working_connection")
    def test_device_update_config_in_progress(
        self, mocked_get_working_connection, mocked_update_config, mocked_sleep
    ):
        conf = self._prepare_conf_object()

        with self.subTest("More than one update_config task active for the device"):
            with mock.patch("celery.app.control.Inspect.active") as mocked_active:
                mocked_active.return_value = {
                    "task": [
                        {
                            "name": _TASK_NAME,
                            "args": [str(conf.device.pk)],
                            "id": str(uuid4()),
                        }
                    ]
                }
                conf.config = {"general": {"timezone": "UTC"}}
                conf.full_clean()
                conf.save()
                mocked_active.assert_called_once()
                mocked_get_working_connection.assert_not_called()
                mocked_update_config.assert_not_called()

        Config.objects.update(status="applied")
        mocked_get_working_connection.return_value = (
            conf.device.deviceconnection_set.first()
        )
        with self.subTest("Only one task is active for the device"):
            task_id = str(uuid4())
            with mock.patch(
                "celery.app.control.Inspect.active"
            ) as mocked_active, mock.patch(
                "celery.app.task.Context.id",
                new_callable=mock.PropertyMock,
                return_value=task_id,
            ):
                mocked_active.return_value = {
                    "task": [
                        {
                            "name": _TASK_NAME,
                            "args": [str(conf.device.pk)],
                            "id": task_id,
                        }
                    ]
                }
                conf.config = {"general": {"timezone": "Asia/Kolkata"}}
                conf.full_clean()
                conf.save()
                mocked_active.assert_called_once()
                mocked_get_working_connection.assert_called_once()
                mocked_update_config.assert_called_once()

    @mock.patch("time.sleep")
    @mock.patch.object(DeviceConnection, "update_config")
    @mock.patch.object(DeviceConnection, "get_working_connection")
    def test_device_update_config_not_in_progress(
        self, mocked_get_working_connection, mocked_update_config, mocked_sleep
    ):
        conf = self._prepare_conf_object()
        mocked_get_working_connection.return_value = (
            conf.device.deviceconnection_set.first()
        )

        with mock.patch("celery.app.control.Inspect.active") as mocked_active:
            # Mock a task running for a different device (args is different)
            mocked_active.return_value = {
                "task": [
                    {
                        "name": _TASK_NAME,
                        "args": ["another-device-id"],  # Different device
                        "id": "different-task-id",
                    }
                ]
            }
            conf.config = {"general": {"timezone": "UTC"}}
            conf.full_clean()
            conf.save()
            mocked_active.assert_called_once()
            mocked_get_working_connection.assert_called_once()
            mocked_update_config.assert_called_once()

    @mock.patch(_connect_path)
    def test_schedule_command_called(self, connect_mocked):
        dc = self._create_device_connection()
        command = Command(
            device=dc.device,
            connection=dc,
            type="custom",
            input={"command": "echo test"},
        )
        command.full_clean()
        with mock.patch(_exec_command_path) as mocked:
            mocked.return_value = self._exec_command_return_value()
            command.save()
            connect_mocked.assert_called_once()
            mocked.assert_called_once()
        command.refresh_from_db()
        self.assertEqual(command.status, "success")
        self.assertEqual(command.output, "mocked\n")

    def test_auto_add_to_existing_device_on_edit(self):
        d = self._create_device(organization=self._get_org())
        self._create_config(device=d)
        self.assertEqual(d.deviceconnection_set.count(), 0)
        c = self._create_credentials(auto_add=False, organization=None)
        org2 = Organization.objects.create(name="org2", slug="org2")
        self._create_credentials(name="cred2", auto_add=True, organization=org2)
        d.refresh_from_db()
        self.assertEqual(d.deviceconnection_set.count(), 0)
        c.auto_add = True
        c.full_clean()
        c.save()
        d.refresh_from_db()
        self.assertEqual(d.deviceconnection_set.count(), 1)
        self.assertEqual(d.deviceconnection_set.first().credentials, c)
        # ensure further edits are idempotent
        c.name = "changed"
        c.full_clean()
        c.save()
        d.refresh_from_db()
        self.assertEqual(d.deviceconnection_set.count(), 1)
        self.assertEqual(d.deviceconnection_set.first().credentials, c)

    def test_auto_add_to_existing_device_on_creation(self):
        d = self._create_device(organization=self._get_org())
        self._create_config(device=d)
        self.assertEqual(d.deviceconnection_set.count(), 0)
        c = self._create_credentials(auto_add=True, organization=None)
        org2 = Organization.objects.create(name="org2", slug="org2")
        self._create_credentials(name="cred2", auto_add=True, organization=org2)
        d.refresh_from_db()
        self.assertEqual(d.deviceconnection_set.count(), 1)
        self.assertEqual(d.deviceconnection_set.first().credentials, c)
        self._create_credentials(name="cred3", auto_add=False, organization=None)
        d.refresh_from_db()
        self.assertEqual(d.deviceconnection_set.count(), 1)
        self.assertEqual(d.deviceconnection_set.first().credentials, c)

    @mock.patch.object(DeviceConnection, "update_config")
    @mock.patch.object(DeviceConnection, "get_working_connection")
    @mock.patch("time.sleep")
    def test_deactivating_device_update_config(
        self, mocked_sleep, mocked_get_working_connection, mocked_update_config
    ):
        conf = self._prepare_conf_object()
        conf.save()
        mocked_get_working_connection.reset_mock()
        mocked_update_config.reset_mock()
        mocked_get_working_connection.return_value = (
            conf.device.deviceconnection_set.first()
        )
        # Deactivate the device
        conf.device.deactivate()
        # Ensure that the config status is set to "deactivating" and
        # update_config is called to apply the empty configuration for deactivated
        # devices.
        conf.refresh_from_db()
        self.assertEqual(conf.status, "deactivating")
        mocked_get_working_connection.assert_called_once_with(conf.device)
        mocked_update_config.assert_called_once()

    def test_chunk_size(self):
        org = self._get_org()
        self._create_config(device=self._create_device(organization=org))
        self._create_config(
            device=self._create_device(
                organization=org, name="device2", mac_address="22:22:22:22:22:22"
            )
        )
        self._create_config(
            device=self._create_device(
                organization=org, name="device3", mac_address="33:33:33:33:33:33"
            )
        )
        with self.assertNumQueries(32):
            credential = self._create_credentials(auto_add=True, organization=org)
        self.assertEqual(credential.deviceconnection_set.count(), 3)

        with mock.patch.object(Credentials, "chunk_size", 2):
            with self.assertNumQueries(35):
                credential = self._create_credentials(
                    name="Mocked Credential", auto_add=True, organization=org
                )

    @mock.patch.object(Command, "_schedule_command")
    def test_batch_command_broadcast_deferred_to_commit(self, schedule_command):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)
        dc = self._create_device_connection(device=device)
        batch = self._create_batch_command(organization=org)
        command_opts = dict(
            batch_command=batch,
            device=device,
            connection=dc,
            type=batch.type,
            input={"command": "echo test"},
        )

        def channel_layer():
            layer = mock.MagicMock()
            layer.group_send = mock.AsyncMock()
            return layer

        with self.subTest("nothing is sent before the transaction commits"):
            layer = channel_layer()
            with mock.patch.object(
                handlers.layers, "get_channel_layer", return_value=layer
            ):
                with transaction.atomic():
                    command = Command.objects.create(**command_opts)
                    layer.group_send.assert_not_called()
                layer.group_send.assert_called_once()
            group, event = layer.group_send.call_args[0]
            self.assertEqual(group, f"config.batchcommand-{batch.pk}")
            self.assertEqual(event["type"], "send.update")
            self.assertEqual(event["data"]["type"], "command_update")
            self.assertEqual(event["data"]["id"], str(command.pk))
            self.assertEqual(event["data"]["device_name"], device.name)

        with self.subTest("a rolled back command is never broadcast"):
            layer = channel_layer()
            with mock.patch.object(
                handlers.layers, "get_channel_layer", return_value=layer
            ):
                with self.assertRaises(ValueError):
                    with transaction.atomic():
                        Command.objects.create(**command_opts)
                        raise ValueError()
                layer.group_send.assert_not_called()
        self.assertEqual(batch.batch_commands.count(), 1)
