import json
import uuid
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils.timezone import now, timedelta
from packaging.version import parse as parse_version
from rest_framework import VERSION as REST_FRAMEWORK_VERSION
from rest_framework.exceptions import ErrorDetail
from swapper import load_model

from openwisp_controller.tests.utils import TestAdminMixin
from openwisp_users.tests.test_api import AuthenticationMixin

from .. import settings as app_settings
from ..api.views import BatchCommandListView, CommandListCreateView
from ..commands import ORGANIZATION_ENABLED_COMMANDS
from .utils import CreateCommandMixin, CreateConnectionsMixin

Command = load_model("connection", "Command")
DeviceConnection = load_model("connection", "DeviceConnection")
BatchCommand = load_model("connection", "BatchCommand")
command_qs = Command.objects.order_by("-created")
OrganizationUser = load_model("openwisp_users", "OrganizationUser")
Group = load_model("openwisp_users", "Group")
DeviceGroup = load_model("config", "DeviceGroup")
Location = load_model("geo", "Location")
DeviceLocation = load_model("geo", "DeviceLocation")


class TestCommandsAPI(TestCase, AuthenticationMixin, CreateCommandMixin):
    url_namespace = "connection_api"

    def setUp(self):
        self.admin = self._get_admin()
        self.client.force_login(self.admin)
        self.device_conn = self._create_device_connection()
        self.device_id = self.device_conn.device.id

    def _get_path(self, url_name, *args, **kwargs):
        path = reverse(f"{self.url_namespace}:{url_name}", args=args)
        if not kwargs:
            return path
        query_params = []
        for key, value in kwargs.items():
            query_params.append(f"{key}={value}")
        query_string = "&".join(query_params)
        return f"{path}?{query_string}"

    def _get_device_not_found_error(self, device_id):
        return {"detail": ErrorDetail("Not found.", code="not_found")}

    @patch.object(CommandListCreateView, "pagination_page_size", 3, create=True)
    def test_command_list_api(self):
        number_of_commands = 6
        url = self._get_path("device_command_list", self.device_id)
        for _ in range(number_of_commands):
            self._create_command(device_conn=self.device_conn)
        self.assertEqual(command_qs.count(), number_of_commands)

        response = self.client.get(url)

        with self.subTest('Test "page" query in object notification list view'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], number_of_commands)
            self.assertIn(
                self._get_path("device_command_list", self.device_id, page=2),
                response.data["next"],
            )
            self.assertEqual(response.data["previous"], None)
            self.assertEqual(len(response.data["results"]), 3)

            next_response = self.client.get(response.data["next"])
            self.assertEqual(next_response.status_code, 200)
            self.assertEqual(next_response.data["count"], number_of_commands)
            self.assertEqual(
                next_response.data["next"],
                None,
            )
            self.assertIn(
                self._get_path("device_command_list", self.device_id),
                next_response.data["previous"],
            )
            self.assertEqual(len(next_response.data["results"]), 3)

        with self.subTest('Test "page_size" query'):
            page_size = 3
            url = f"{url}?page_size={page_size}"
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], number_of_commands)
            self.assertIn(
                self._get_path(
                    "device_command_list",
                    self.device_id,
                    page=2,
                    page_size=page_size,
                ),
                response.data["next"],
            )
            self.assertEqual(response.data["previous"], None)
            self.assertEqual(len(response.data["results"]), page_size)

            next_response = self.client.get(response.data["next"])
            self.assertEqual(next_response.status_code, 200)
            self.assertEqual(next_response.data["count"], number_of_commands)
            self.assertEqual(next_response.data["next"], None)
            self.assertIn(
                self._get_path(
                    "device_command_list",
                    self.device_id,
                    page_size=page_size,
                ),
                next_response.data["previous"],
            )
            self.assertEqual(len(next_response.data["results"]), page_size)

        with self.subTest("Test individual result object"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            command_obj = response.data["results"][0]
            self.assertIn("id", command_obj)
            self.assertIn("status", command_obj)
            self.assertIn("type", command_obj)
            self.assertIn("input", command_obj)
            self.assertIn("output", command_obj)
            self.assertIn("device", command_obj)
            self.assertIn("connection", command_obj)

        with self.subTest("Test results ordering, recent first"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            created_list = [cmd["created"] for cmd in response.data["results"]]
            sorted_created_list = sorted(created_list, reverse=True)
            self.assertEqual(created_list, sorted_created_list)

    def test_command_create_api(self):
        def test_command_attributes(self, payload):
            self.assertEqual(command_qs.count(), 1)
            command_obj = command_qs.first()
            self.assertEqual(command_obj.device_id, self.device_id)
            self.assertEqual(command_obj.type, payload["type"])
            self.assertEqual(command_obj.input, payload["input"])
            command_qs.delete()

        url = self._get_path("device_command_list", self.device_id)

        with self.subTest('Test "reboot" command'):
            payload = {
                "type": "reboot",
                "input": None,
            }
            response = self.client.post(
                url,
                data=payload,
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            test_command_attributes(self, payload)

        with self.subTest('Test "reset_password" command'):
            payload = {
                "type": "change_password",
                "input": {"password": "ass@1234", "confirm_password": "Pass@1234"},
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            test_command_attributes(self, payload)

        with self.subTest('Test "custom" command'):
            payload = {
                "type": "custom",
                "input": {"command": "echo test"},
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            test_command_attributes(self, payload)

    # for ensuring that only related connections are shown
    def test_available_connections(self):
        device = self._create_device(
            name="default.test.device2", mac_address="12:23:34:45:56:67"
        )
        self._create_config(device=device)
        credentials_2 = self._create_credentials(name="Test Credentials 2")
        device_conn2 = self._create_device_connection(
            device=device, credentials=credentials_2
        )
        url = self._get_path("device_command_list", self.device_id)
        response = self.client.get(url, {"format": "api"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(self.device_conn.id))
        self.assertNotContains(response, device_conn2.id)

    def test_command_details_api(self):
        command_obj = self._create_command(device_conn=self.device_conn)
        url = self._get_path("device_command_details", self.device_id, command_obj.id)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(command_obj.id))
        self.assertEqual(response.data["status"], command_obj.status)
        self.assertEqual(response.data["input"], command_obj.input_data)
        self.assertEqual(response.data["output"], command_obj.output)
        self.assertEqual(response.data["device"], str(command_obj.device_id))
        self.assertEqual(response.data["connection"], str(command_obj.connection_id))
        # These are hard coded because API reverts more verbose response
        self.assertEqual(response.data["type"], "Custom commands")

    def test_bearer_authentication(self):
        self.client.logout()
        command_obj = self._create_command(device_conn=self.device_conn)
        token = self._obtain_auth_token(username="admin", password="tester")

        with self.subTest("Test creating command"):
            url = self._get_path("device_command_list", self.device_id)
            payload = {
                "type": "custom",
                "input": {"command": "echo test"},
            }
            response = self.client.post(
                url,
                data=payload,
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 201)
            self.assertIn("id", response.data)

        with self.subTest("Test retrieving command"):
            url = self._get_path(
                "device_command_details", self.device_id, command_obj.id
            )
            response = self.client.get(
                url,
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("id", response.data)

        with self.subTest("Test listing command"):
            url = self._get_path("device_command_list", self.device_id)
            response = self.client.get(
                url,
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data["results"]), 2)

    def test_endpoints_for_non_existent_device(self):
        device_id = uuid.uuid4()
        device_not_found = self._get_device_not_found_error(device_id)

        with self.subTest("Test listing commands"):
            url = self._get_path("device_command_list", device_id)
            response = self.client.get(
                url,
            )
            self.assertEqual(response.status_code, 404)
            self.assertDictEqual(response.data, device_not_found)

        with self.subTest("Test creating commands"):
            url = self._get_path("device_command_list", device_id)
            payload = {
                "type": "custom",
                "input": {"command": "echo test"},
            }
            response = self.client.post(
                url, data=payload, content_type="application/json"
            )
            self.assertEqual(response.status_code, 404)
            self.assertDictEqual(response.data, device_not_found)

        with self.subTest("Test retrieving commands"):
            url = self._get_path("device_command_details", device_id, uuid.uuid4())
            response = self.client.get(
                url,
            )
            self.assertEqual(response.status_code, 404)
            self.assertDictEqual(response.data, device_not_found)

    def test_endpoints_for_deactivated_device(self):
        command = self._create_command(device_conn=self.device_conn)
        self.device_conn.device.deactivate()

        with self.subTest("Test listing commands"):
            url = self._get_path("device_command_list", self.device_id)
            response = self.client.get(
                url,
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test creating commands"):
            url = self._get_path("device_command_list", self.device_id)
            payload = {
                "type": "custom",
                "input": {"command": "echo test"},
            }
            response = self.client.post(
                url, data=payload, content_type="application/json"
            )
            self.assertEqual(response.status_code, 403)

        with self.subTest("Test retrieving commands"):
            url = self._get_path("device_command_details", self.device_id, command.id)
            response = self.client.get(
                url,
            )
            self.assertEqual(response.status_code, 200)

    def _test_command_endpoints(
        self,
        list_path,
        detail_path,
        expected_status,
    ):
        with self.subTest("List operation"):
            response = self.client.get(list_path)
            self.assertEqual(response.status_code, expected_status["list"])

        with self.subTest("Create operation"):
            response = self.client.post(
                list_path,
                data={"type": "custom", "input": {"command": "echo test"}},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, expected_status["create"])

        with self.subTest("Retrieve operation"):
            response = self.client.get(detail_path)
            self.assertEqual(response.status_code, expected_status["retrieve"])

    def test_endpoints_for_org_operators_own_org(self):
        self.client.logout()
        operator = self._create_operator(organizations=[self._get_org()])
        self.client.force_login(operator)
        list_path = self._get_path("device_command_list", self.device_id)
        command = self._create_command(device_conn=self.device_conn)
        detail_path = self._get_path(
            "device_command_details", self.device_id, command.id
        )
        self._test_command_endpoints(
            list_path,
            detail_path,
            expected_status={"list": 200, "create": 201, "retrieve": 200},
        )

    def test_endpoints_for_org_operator_different_org(self):
        org2 = self._create_org(name="org2", slug="org2")
        org2_admin = self._create_operator(organizations=[org2])
        org1_command = self._create_command(device_conn=self.device_conn)
        list_path = self._get_path("device_command_list", self.device_id)
        detail_path = self._get_path(
            "device_command_details", self.device_id, org1_command.id
        )

        self.client.logout()
        self.client.force_login(org2_admin)
        self._test_command_endpoints(
            list_path,
            detail_path,
            expected_status={"list": 404, "create": 404, "retrieve": 404},
        )

    def test_unauthenticated_user(self):
        list_path = self._get_path("device_command_list", self.device_id)
        command = self._create_command(device_conn=self.device_conn)
        self.client.logout()
        detail_path = self._get_path(
            "device_command_details", self.device_id, command.id
        )
        self._test_command_endpoints(
            list_path,
            detail_path,
            expected_status={"list": 401, "create": 401, "retrieve": 401},
        )

    def test_non_existent_command(self):
        url = self._get_path("device_command_list", self.device_id)
        with patch.dict(
            ORGANIZATION_ENABLED_COMMANDS,
            {str(self.device_conn.device.organization_id): ("reboot",)},
        ):
            payload = {
                "type": "custom",
                "input": {"command": "echo test"},
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(
                '"custom" is not a valid choice.',
                response.data["type"][0],
            )

    def test_create_command_without_connection(self):
        device = self._create_device(
            name="default.test.device2", mac_address="11:22:33:44:55:66"
        )
        url = self._get_path("device_command_list", device.pk)
        payload = {
            "type": "custom",
            "input": {"command": "echo test"},
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Device has no credentials assigned",
            response.data["device"][0],
        )


class TestConnectionApi(
    TestAdminMixin, AuthenticationMixin, TestCase, CreateConnectionsMixin
):
    def setUp(self):
        super().setUp()
        self._login()

    def test_get_credentials_list(self):
        self._create_credentials()
        path = reverse("connection_api:credential_list")
        with self.assertNumQueries(3):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        with self.subTest("Check ordering of credentials"):
            cred_old = self._create_credentials(name="Old Credential")
            cred_old.created = now() - timedelta(days=1)
            cred_old.save()
            self._create_credentials(name="Newest Credential")
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            created_list = [cred["created"] for cred in response.data["results"]]
            sorted_created = sorted(created_list, reverse=True)
            self.assertEqual(created_list, sorted_created)

    def test_filter_credentials_list(self):
        cred_1 = self._create_credentials(name="Credential One")
        org1 = self._create_org(name="org1")
        cred_2 = self._create_credentials(name="Credential Two", organization=org1)
        change_perm = Permission.objects.filter(codename="change_credentials")
        user = self._get_user()
        user.user_permissions.add(*change_perm)
        OrganizationUser.objects.create(user=user, organization=org1, is_admin=True)
        self.client.force_login(user)
        path = reverse("connection_api:credential_list")
        with self.assertNumQueries(5):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertContains(response, cred_2.id)
        self.assertNotContains(response, cred_1.id)

    def test_post_credential_list(self):
        path = reverse("connection_api:credential_list")
        data = {
            "connector": "openwisp_controller.connection.connectors.ssh.Ssh",
            "name": "Change Test credentials",
            "organization": self._get_org().pk,
            "auto_add": False,
            "params": {"username": "roOT", "password": "Pa$$w0Rd", "port": 22},
        }
        with self.assertNumQueries(7):
            response = self.client.post(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 201)

    def test_get_credential_detail(self):
        cred = self._create_credentials()
        path = reverse("connection_api:credential_detail", args=(cred.pk,))
        with self.assertNumQueries(2):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_put_credential_detail(self):
        org1 = self._get_org()
        cred = self._create_credentials()
        path = reverse("connection_api:credential_detail", args=(cred.pk,))
        data = {
            "connector": "openwisp_controller.connection.connectors.ssh.Ssh",
            "name": "Change Test credentials",
            "organization": org1.pk,
            "auto_add": False,
            "params": {
                "username": "root_change",
                "password": "passwordchange",
                "port": 22,
            },
        }
        expected_queries = (
            8 if parse_version(REST_FRAMEWORK_VERSION) >= parse_version("3.15") else 7
        )
        with self.assertNumQueries(expected_queries):
            response = self.client.put(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], data["name"])
        self.assertEqual(response.data["organization"], data["organization"])
        self.assertEqual(
            response.data["params"]["username"], data["params"]["username"]
        )
        self.assertEqual(
            response.data["params"]["password"], data["params"]["password"]
        )

    def test_patch_credential_detail(self):
        cred = self._create_credentials()
        path = reverse("connection_api:credential_detail", args=(cred.pk,))
        data = {"name": "Change Test credentials"}
        with self.assertNumQueries(7):
            response = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Change Test credentials")

    def test_delete_credential_detail(self):
        cred = self._create_credentials()
        path = reverse("connection_api:credential_detail", args=(cred.pk,))
        with self.assertNumQueries(4):
            response = self.client.delete(path)
        self.assertEqual(response.status_code, 204)

    def test_get_deviceconnection_list(self):
        d1 = self._create_device()
        path = reverse("connection_api:deviceconnection_list", args=(d1.pk,))
        with self.assertNumQueries(4):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        with self.subTest("Check ordering of device connections"):
            self._create_config(device=d1)
            creds = [self._create_credentials(name=f"Cred {i}") for i in range(3)]
            creds[0].created = now() - timedelta(days=1)
            creds[0].save()
            for cred in creds:
                DeviceConnection.objects.create(device=d1, credentials=cred)
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            created_list = [conn["created"] for conn in response.data["results"]]
            sorted_created = sorted(created_list, reverse=True)
            self.assertEqual(created_list, sorted_created)

    def test_post_deviceconnection_list(self):
        d1 = self._create_device()
        self._create_config(device=d1)
        path = reverse("connection_api:deviceconnection_list", args=(d1.pk,))
        data = {
            "credentials": self._get_credentials().pk,
            "update_strategy": app_settings.UPDATE_STRATEGIES[0][0],
            "enabled": True,
            "failure_reason": "",
        }
        with self.assertNumQueries(12):
            response = self.client.post(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 201)

    def test_post_deviceconenction_with_no_config_device(self):
        d1 = self._create_device()
        path = reverse("connection_api:deviceconnection_list", args=(d1.pk,))
        data = {
            "credentials": self._get_credentials().pk,
            "update_strategy": "",
            "enabled": True,
            "failure_reason": "",
        }
        with self.assertNumQueries(12):
            response = self.client.post(path, data, content_type="application/json")
        error_msg = """
            the update strategy can be determined automatically only if
            the device has a configuration specified, because it is
            inferred from the configuration backend. Please select
            the update strategy manually.
        """
        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            " ".join(error_msg.split()), response.data["update_strategy"][0].title()
        )

    def test_get_deviceconnection_detail(self):
        dc = self._create_device_connection()
        d1 = dc.device.id
        path = reverse("connection_api:deviceconnection_detail", args=(d1, dc.pk))
        with self.assertNumQueries(5):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_put_devceconnection_detail(self):
        dc = self._create_device_connection()
        d1 = dc.device.id
        path = reverse("connection_api:deviceconnection_detail", args=(d1, dc.pk))
        self.assertEqual(dc.update_strategy, app_settings.UPDATE_STRATEGIES[0][0])
        data = {
            "credentials": self._get_credentials().pk,
            "update_strategy": app_settings.UPDATE_STRATEGIES[1][0],
            "enabled": False,
            "failure_reason": "",
        }
        with self.assertNumQueries(13):
            response = self.client.put(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["update_strategy"], app_settings.UPDATE_STRATEGIES[1][0]
        )
        self.assertEqual(response.data["credentials"], self._get_credentials().pk)

    def test_patch_deviceconnectoin_detail(self):
        dc = self._create_device_connection()
        d1 = dc.device.id
        path = reverse("connection_api:deviceconnection_detail", args=(d1, dc.pk))
        self.assertEqual(dc.update_strategy, app_settings.UPDATE_STRATEGIES[0][0])
        data = {"update_strategy": app_settings.UPDATE_STRATEGIES[1][0]}
        with self.assertNumQueries(13):
            response = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["update_strategy"], app_settings.UPDATE_STRATEGIES[1][0]
        )

    def test_delete_deviceconnection_detail(self):
        dc = self._create_device_connection()
        d1 = dc.device.id
        path = reverse("connection_api:deviceconnection_detail", args=(d1, dc.pk))
        with self.assertNumQueries(10):
            response = self.client.delete(path)
        self.assertEqual(response.status_code, 204)

    def test_bearer_authentication(self):
        self.client.logout()
        token = self._obtain_auth_token(username="admin", password="tester")
        credentials = self._create_credentials(auto_add=True)
        device = self._create_config(organization=credentials.organization).device
        device_conn = device.deviceconnection_set.first()

        with self.subTest("Test CredentialListCreateView"):
            response = self.client.get(
                reverse("connection_api:credential_list"),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test CredentialDetailView"):
            response = self.client.get(
                reverse("connection_api:credential_detail", args=[credentials.id]),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test DeviceConnenctionListCreateView"):
            response = self.client.get(
                reverse("connection_api:deviceconnection_list", args=[device.id]),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test DeviceConnectionDetailView"):
            response = self.client.get(
                reverse(
                    "connection_api:deviceconnection_detail",
                    args=[device.id, device_conn.id],
                ),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

    def test_deactivated_device(self):
        credentials = self._create_credentials(auto_add=True)
        device = self._create_config(organization=credentials.organization).device
        device_conn = device.deviceconnection_set.first()
        create_api_path = reverse(
            "connection_api:deviceconnection_list", args=(device.pk,)
        )
        detail_api_path = reverse(
            "connection_api:deviceconnection_detail",
            args=[device.id, device_conn.id],
        )
        device.deactivate()

        with self.subTest("Test creating DeviceConnection"):
            response = self.client.post(
                create_api_path,
                data={
                    "credentials": credentials.pk,
                    "update_strategy": app_settings.UPDATE_STRATEGIES[0][0],
                    "enabled": True,
                    "failure_reason": "",
                },
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 403)

        with self.subTest("Test listing DeviceConnection"):
            response = self.client.get(
                create_api_path,
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test retrieving DeviceConnection detail"):
            response = self.client.get(
                detail_api_path,
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test updating DeviceConnection"):
            response = self.client.put(
                detail_api_path,
                {
                    "credentials": credentials.pk,
                    "update_strategy": app_settings.UPDATE_STRATEGIES[1][0],
                    "enabled": False,
                    "failure_reason": "",
                },
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 403)

            response = self.client.patch(
                detail_api_path, {"enabled": False}, content_type="application/json"
            )
            self.assertEqual(response.status_code, 403)

        with self.subTest("Test deleting DeviceConnection"):
            response = self.client.delete(
                detail_api_path,
            )
            self.assertEqual(response.status_code, 403)

    def _test_deviceconnection_endpoints(
        self,
        device_id,
        list_path,
        detail_path,
        expected_status,
    ):
        with self.subTest("List operation"):
            response = self.client.get(list_path)
            self.assertEqual(response.status_code, expected_status["list"])

        with self.subTest("Create operation"):
            response = self.client.post(
                list_path,
                data={
                    "credentials": self._get_credentials(name="New Credentials").pk,
                    "update_strategy": app_settings.UPDATE_STRATEGIES[0][0],
                    "enabled": True,
                    "failure_reason": "",
                },
                content_type="application/json",
            )

            self.assertEqual(response.status_code, expected_status["create"])

        with self.subTest("Retrieve operation"):
            response = self.client.get(detail_path)
            self.assertEqual(response.status_code, expected_status["retrieve"])

        with self.subTest("Update operation"):
            response = self.client.put(
                detail_path,
                {
                    "credentials": self._get_credentials().pk,
                    "update_strategy": app_settings.UPDATE_STRATEGIES[1][0],
                    "enabled": False,
                    "failure_reason": "",
                },
                content_type="application/json",
            )
            self.assertEqual(response.status_code, expected_status["update"])

        with self.subTest("Partial update operation"):
            response = self.client.patch(
                detail_path, {"enabled": False}, content_type="application/json"
            )
            self.assertEqual(response.status_code, expected_status["patch"])

        with self.subTest("Delete operation"):
            response = self.client.delete(detail_path)
            self.assertEqual(response.status_code, expected_status["delete"])

    def test_deviceconnection_endpoints_for_org_operators_own_org(self):
        self.client.logout()
        operator = self._create_operator(organizations=[self._get_org()])
        self.client.force_login(operator)
        device = self._create_device()
        self._create_config(device=device)
        dc = self._create_device_connection(device=device)
        list_path = reverse("connection_api:deviceconnection_list", args=(device.pk,))
        detail_path = reverse(
            "connection_api:deviceconnection_detail", args=(device.pk, dc.pk)
        )
        self._test_deviceconnection_endpoints(
            device.pk,
            list_path,
            detail_path,
            expected_status={
                "list": 200,
                "create": 201,
                "retrieve": 200,
                "update": 200,
                "patch": 200,
                "delete": 204,
            },
        )

    def test_deviceconnection_endpoints_for_org_operator_different_org(self):
        org2 = self._create_org(name="org2", slug="org2")
        org2_operator = self._create_operator(organizations=[org2])
        device = self._create_device()
        self._create_config(device=device)
        dc = self._create_device_connection(device=device)
        list_path = reverse("connection_api:deviceconnection_list", args=(device.pk,))
        detail_path = reverse(
            "connection_api:deviceconnection_detail", args=(device.pk, dc.pk)
        )
        self.client.logout()
        self.client.force_login(org2_operator)
        self._test_deviceconnection_endpoints(
            device.pk,
            list_path,
            detail_path,
            expected_status={
                "list": 404,
                "create": 404,
                "retrieve": 404,
                "update": 404,
                "patch": 404,
                "delete": 404,
            },
        )

    def test_deviceconnection_unauthenticated_user(self):
        device = self._create_device()
        self._create_config(device=device)
        dc = self._create_device_connection(device=device)
        list_path = reverse("connection_api:deviceconnection_list", args=(device.pk,))
        detail_path = reverse(
            "connection_api:deviceconnection_detail", args=(device.pk, dc.pk)
        )
        self.client.logout()
        self._test_deviceconnection_endpoints(
            device.pk,
            list_path,
            detail_path,
            expected_status={
                "list": 401,
                "create": 401,
                "retrieve": 401,
                "update": 401,
                "patch": 401,
                "delete": 401,
            },
        )


class TestBatchCommandsAPI(
    TestAdminMixin, AuthenticationMixin, TestCase, CreateConnectionsMixin
):
    url_namespace = "connection_api"

    def setUp(self):
        super().setUp()
        self._login()

    def test_batch_command_list(self):
        org = self._get_org()
        url = reverse("connection_api:batch_command_list")
        for _ in range(3):
            self._create_batch_command(organization=org)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 3)
        created_list = [cmd["created"] for cmd in response.data["results"]]
        sorted_created = sorted(created_list, reverse=True)
        self.assertEqual(created_list, sorted_created)
        result = response.data["results"][0]
        self.assertIn("id", result)
        self.assertIn("status", result)
        self.assertIn("type", result)
        self.assertIn("input", result)
        self.assertIn("device_count", result)
        self.assertIn("created", result)
        self.assertEqual(result["device_count"], 0)

        with patch.object(BatchCommandListView, "pagination_page_size", 2, create=True):
            with self.subTest("pagination page 1"):
                for _ in range(2):
                    self._create_batch_command(organization=org)
                response = self.client.get(url + "?page=1")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.data["results"]), 2)

            with self.subTest("pagination page 2"):
                response = self.client.get(url + "?page=2")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.data["results"]), 2)

            with self.subTest("pagination page 3 (partial)"):
                response = self.client.get(url + "?page=3")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.data["results"]), 1)

    def test_batch_command_detail(self):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)
        batch = self._create_batch_command(organization=org, devices=[device])
        url = reverse("connection_api:batch_command_detail", args=[batch.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(batch.pk))
        self.assertEqual(response.data["status"], batch.status)
        self.assertEqual(response.data["type"], batch.type)
        self.assertEqual(response.data["input"], batch.input)
        self.assertIn("devices", response.data)
        self.assertEqual(response.data["devices"], [str(device.pk)])
        self.assertEqual(response.data["device_count"], 1)

    def test_batch_command_dry_run_endpoint(self):
        org = self._get_org()
        device1 = self._create_device(
            name="dryf-dev1",
            mac_address="00:11:22:33:44:d1",
            organization=org,
        )
        self._create_config(device=device1)
        device2 = self._create_device(
            name="dryf-dev2",
            mac_address="00:11:22:33:44:d2",
            organization=org,
        )
        self._create_config(device=device2)
        group = DeviceGroup.objects.create(name="dryf-group", organization=org)
        device1.group = group
        device1.save()
        location = Location.objects.create(
            name="dryf-loc",
            type="indoor",
            organization=org,
        )
        DeviceLocation.objects.create(content_object=device2, location=location)

        base_url = reverse("connection_api:batch_command_execute")

        with self.subTest("dry run with explicit devices"):
            url = "{0}?organization={1}&devices={2}".format(
                base_url,
                str(org.pk),
                str(device1.pk),
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["devices"], [str(device1.pk)])

        with self.subTest("dry run with group"):
            url = "{0}?organization={1}&group={2}".format(
                base_url,
                str(org.pk),
                str(group.pk),
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn(str(device1.pk), response.data["devices"])
            self.assertNotIn(str(device2.pk), response.data["devices"])

        with self.subTest("dry run with location"):
            url = "{0}?organization={1}&location={2}".format(
                base_url,
                str(org.pk),
                str(location.pk),
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn(str(device2.pk), response.data["devices"])
            self.assertNotIn(str(device1.pk), response.data["devices"])

        with self.subTest("dry run with group and location"):
            DeviceLocation.objects.create(content_object=device1, location=location)
            url = "{0}?organization={1}&group={2}&location={3}".format(
                base_url,
                str(org.pk),
                str(group.pk),
                str(location.pk),
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn(str(device1.pk), response.data["devices"])
            self.assertNotIn(str(device2.pk), response.data["devices"])

        with self.subTest("dry run org-wide"):
            url = "{0}?organization={1}".format(base_url, str(org.pk))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn(str(device1.pk), response.data["devices"])
            self.assertIn(str(device2.pk), response.data["devices"])

        with self.subTest("dry run with type and input"):
            url = (
                "{0}?organization={1}&type=custom"
                "&input=%7B%22command%22%3A%22uptime%22%7D"
            ).format(base_url, str(org.pk))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn(str(device1.pk), response.data["devices"])
            self.assertIn(str(device2.pk), response.data["devices"])

    def test_batch_command_endpoints_no_of_queries(self):
        with self.subTest("list queries"):
            org = self._get_org()
            devices = []
            for i in range(2):
                d = self._create_device(
                    name=f"q-dev-{i}",
                    mac_address=f"00:11:22:33:44:{i:02x}",
                    organization=org,
                )
                self._create_config(device=d)
                devices.append(d)
            self._create_batch_command(organization=org, devices=devices)
            url = reverse("connection_api:batch_command_list")
            with self.assertNumQueries(3):
                response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 1)

        with self.subTest("detail queries"):
            url = reverse(
                "connection_api:batch_command_detail",
                args=[response.data["results"][0]["id"]],
            )
            with self.assertNumQueries(3):
                response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        with self.subTest("execute queries"):
            org = self._get_org()
            devices = []
            for i in range(3):
                d = self._create_device(
                    name=f"q-exec-{i}",
                    mac_address=f"00:11:22:33:44:{i + 0x10:02x}",
                    organization=org,
                )
                self._create_config(device=d)
                devices.append(d)
            payload = {
                "organization": str(org.pk),
                "type": "custom",
                "input": {"command": "echo test"},
                "label": "test-label",
                "devices": [str(d.pk) for d in devices],
            }
            url = reverse("connection_api:batch_command_execute")
            with self.assertNumQueries(15):
                response = self.client.post(
                    url,
                    data=json.dumps(payload),
                    content_type="application/json",
                )
            self.assertEqual(response.status_code, 201)
            self.assertIn("batch", response.data)
            batch = BatchCommand.objects.get(pk=response.data["batch"])
            self.assertEqual(batch.devices.count(), 3)
            self.assertCountEqual(
                batch.devices.values_list("pk", flat=True),
                [d.pk for d in devices],
            )

        with self.subTest("execute queries with group"):
            org = self._get_org()
            group = DeviceGroup.objects.create(name="q-exec-group", organization=org)
            devices = []
            for i in range(3):
                d = self._create_device(
                    name=f"q-exec-grp-{i}",
                    mac_address=f"00:11:22:33:44:{0x30 + i:02x}",
                    organization=org,
                )
                self._create_config(device=d)
                d.group = group
                d.save()
                devices.append(d)
            payload = {
                "organization": str(org.pk),
                "type": "custom",
                "input": {"command": "echo test"},
                "label": "test-label",
                "group": str(group.pk),
            }
            url = reverse("connection_api:batch_command_execute")
            with self.assertNumQueries(14):
                response = self.client.post(
                    url,
                    data=json.dumps(payload),
                    content_type="application/json",
                )
            self.assertEqual(response.status_code, 201)

        with self.subTest("execute queries org-wide"):
            org = self._get_org()
            devices = []
            for i in range(3):
                d = self._create_device(
                    name=f"q-exec-all-{i}",
                    mac_address=f"00:11:22:33:44:{0x40 + i:02x}",
                    organization=org,
                )
                self._create_config(device=d)
                devices.append(d)
            payload = {
                "organization": str(org.pk),
                "type": "custom",
                "input": {"command": "echo test"},
                "label": "test-label",
            }
            url = reverse("connection_api:batch_command_execute")
            with self.assertNumQueries(12):
                response = self.client.post(
                    url,
                    data=json.dumps(payload),
                    content_type="application/json",
                )
            self.assertEqual(response.status_code, 201)

    def test_batch_command_execute_org_has_no_devices(self):
        org = self._get_org()
        payload = {
            "organization": str(org.pk),
            "type": "custom",
            "input": {"command": "echo test"},
            "label": "test-label",
        }
        url = reverse("connection_api:batch_command_execute")
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            ["No devices match the specified criteria."],
        )

    def test_batch_command_execute_disallowed_type(self):
        org = self._get_org()
        url = reverse("connection_api:batch_command_execute")
        with patch.dict(
            ORGANIZATION_ENABLED_COMMANDS,
            {str(org.pk): ("reboot",)},
        ):
            payload = {
                "organization": str(org.pk),
                "type": "custom",
                "input": {"command": "echo test"},
                "label": "test-label",
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(
                '"custom" command is not available for this organization',
                response.data["type"][0],
            )

    def test_batch_command_no_org_only_allowed_to_superuser(self):
        org = self._get_org()
        self.client.logout()
        operator = self._create_operator(organizations=[org])
        add_perm = Permission.objects.get(codename="add_batchcommand")
        operator.user_permissions.add(add_perm)
        self.client.force_login(operator)
        payload = {
            "type": "custom",
            "input": {"command": "echo test"},
            "label": "test-label",
        }
        url = reverse("connection_api:batch_command_execute")
        with self.subTest("POST execute without org"):
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(
                "Only superusers",
                str(response.data),
            )

        with self.subTest("GET dry-run without org"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 400)
            self.assertIn(
                "Only superusers",
                str(response.data),
            )

    def test_superuser_batch_command_execute_without_org(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        device1 = self._create_device(
            name="super-org-dev1",
            mac_address="00:11:22:33:44:81",
            organization=org,
        )
        self._create_config(device=device1)
        device2 = self._create_device(
            name="super-org-dev2",
            mac_address="00:11:22:33:44:82",
            organization=org2,
        )
        self._create_config(device=device2)
        url = reverse("connection_api:batch_command_execute")

        with self.subTest("execute targets all devices globally"):
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "test-label",
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            batch = BatchCommand.objects.get(pk=response.data["batch"])
            self.assertEqual(batch.devices.count(), 2)

        with self.subTest("execute with explicit devices"):
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "test-label",
                        "devices": [str(device1.pk), str(device2.pk)],
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            batch = BatchCommand.objects.get(pk=response.data["batch"])
            self.assertEqual(batch.devices.count(), 2)

        with self.subTest("dry-run targets all devices"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn(str(device1.pk), response.data["devices"])
            self.assertIn(str(device2.pk), response.data["devices"])

        with self.subTest("dry-run with explicit devices"):
            response = self.client.get(
                f"{url}?devices={str(device1.pk)}&devices={str(device2.pk)}"
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn(str(device1.pk), response.data["devices"])
            self.assertIn(str(device2.pk), response.data["devices"])

    def test_superuser_org_auto_set_from_group_and_location(self):
        org = self._get_org()
        device = self._create_device(organization=org)
        self._create_config(device=device)
        self._create_device_connection(device=device)
        url = reverse("connection_api:batch_command_execute")

        with self.subTest("from group"):
            group = DeviceGroup.objects.create(name="infer-group", organization=org)
            group.device_set.add(device)
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "infer-group",
                        "group": str(group.pk),
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            batch = BatchCommand.objects.get(pk=response.data["batch"])
            self.assertEqual(batch.organization, org)
            self.assertEqual(batch.devices.count(), 1)
            self.assertIn(device.pk, batch.devices.values_list("pk", flat=True))

        with self.subTest("from location"):
            location = Location.objects.create(
                name="infer-location",
                organization=org,
                geometry="POINT (12.0 44.0)",
            )
            DeviceLocation.objects.create(content_object=device, location=location)
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "infer-location",
                        "location": str(location.pk),
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            batch = BatchCommand.objects.get(pk=response.data["batch"])
            self.assertEqual(batch.organization, org)
            self.assertEqual(batch.devices.count(), 1)
            self.assertIn(device.pk, batch.devices.values_list("pk", flat=True))

    def test_batch_command_operator_endpoints_on_managed_org(self):
        org = self._get_org()
        self._create_credentials(name="op-cred", organization=org)
        device = self._create_device(
            name="op-dev",
            mac_address="00:11:22:33:44:01",
            organization=org,
        )
        self._create_config(device=device)
        self._create_device_connection(device=device)
        self.client.logout()
        operator = self._create_operator(organizations=[org])
        operator.user_permissions.add(
            Permission.objects.get(codename="add_batchcommand"),
            Permission.objects.get(codename="view_batchcommand"),
        )
        self.client.force_login(operator)
        url = reverse("connection_api:batch_command_execute")

        with self.subTest("execute"):
            payload = {
                "organization": str(org.pk),
                "type": "custom",
                "input": {"command": "echo test"},
                "label": "test-label",
                "devices": [str(device.pk)],
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            self.assertIn("batch", response.data)

        with self.subTest("dry-run"):
            response = self.client.get(
                url,
                data={"organization": str(org.pk)},
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("devices", response.data)

        with self.subTest("execute org-wide"):
            payload = {
                "organization": str(org.pk),
                "type": "custom",
                "input": {"command": "echo test"},
                "label": "test-label",
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            self.assertIn("batch", response.data)

    def test_batch_command_administrator_endpoints_on_managed_org(self):
        org = self._get_org()
        self._create_credentials(name="admin-cred", organization=org)
        device = self._create_device(
            name="admin-dev",
            mac_address="00:11:22:33:44:02",
            organization=org,
        )
        self._create_config(device=device)
        self._create_device_connection(device=device)
        self.client.logout()
        administrator = self._create_administrator(organizations=[org])
        self.client.force_login(administrator)
        url = reverse("connection_api:batch_command_execute")

        with self.subTest("execute"):
            payload = {
                "organization": str(org.pk),
                "type": "custom",
                "input": {"command": "echo test"},
                "label": "test-label",
                "devices": [str(device.pk)],
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            self.assertIn("batch", response.data)

        with self.subTest("dry-run"):
            response = self.client.get(
                url,
                data={"organization": str(org.pk)},
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("devices", response.data)

        with self.subTest("execute org-wide"):
            payload = {
                "organization": str(org.pk),
                "type": "custom",
                "input": {"command": "echo test"},
                "label": "test-label",
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            self.assertIn("batch", response.data)

    def test_batch_command_operator_endpoints_on_non_managed_org(self):
        org1 = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        self._create_credentials(name="op-nm-cred", organization=org1)
        device = self._create_device(
            name="op-nm-dev",
            mac_address="00:11:22:33:44:03",
            organization=org1,
        )
        self._create_config(device=device)
        self._create_device_connection(device=device)
        self.client.logout()
        operator = self._create_operator(organizations=[org1])
        operator.user_permissions.add(
            Permission.objects.get(codename="add_batchcommand"),
            Permission.objects.get(codename="view_batchcommand"),
        )
        self.client.force_login(operator)
        url = reverse("connection_api:batch_command_execute")

        with self.subTest("execute"):
            payload = {
                "organization": str(org2.pk),
                "type": "custom",
                "input": {"command": "echo test"},
                "label": "test-label",
                "devices": [str(device.pk)],
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)

        with self.subTest("dry-run"):
            response = self.client.get(
                url,
                data={"organization": str(org2.pk)},
            )
            self.assertEqual(response.status_code, 400)

        with self.subTest("execute org-wide"):
            payload = {
                "organization": str(org2.pk),
                "type": "custom",
                "input": {"command": "echo test"},
                "label": "test-label",
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)

    def test_batch_command_administrator_endpoints_on_non_managed_org(self):
        org1 = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        self._create_credentials(name="admin-nm-cred", organization=org1)
        device = self._create_device(
            name="admin-nm-dev",
            mac_address="00:11:22:33:44:04",
            organization=org1,
        )
        self._create_config(device=device)
        self._create_device_connection(device=device)
        self.client.logout()
        administrator = self._create_administrator(organizations=[org1])
        self.client.force_login(administrator)
        url = reverse("connection_api:batch_command_execute")

        with self.subTest("execute"):
            payload = {
                "organization": str(org2.pk),
                "type": "custom",
                "input": {"command": "echo test"},
                "label": "test-label",
                "devices": [str(device.pk)],
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)

        with self.subTest("dry-run"):
            response = self.client.get(
                url,
                data={"organization": str(org2.pk)},
            )
            self.assertEqual(response.status_code, 400)

        with self.subTest("execute org-wide"):
            payload = {
                "organization": str(org2.pk),
                "type": "custom",
                "input": {"command": "echo test"},
                "label": "test-label",
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)

    def test_batch_command_endpoints_organization_scoped(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        batch_org1 = self._create_batch_command(organization=org)
        batch_org2 = self._create_batch_command(organization=org2)
        self.client.logout()
        operator = self._create_operator(organizations=[org])
        view_perm = Permission.objects.get(codename="view_batchcommand")
        operator.user_permissions.add(view_perm)
        self.client.force_login(operator)

        with self.subTest("list scoped to own org"):
            url = reverse("connection_api:batch_command_list")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 1)

        with self.subTest("detail cross-org"):
            url = reverse(
                "connection_api:batch_command_detail",
                args=[batch_org2.pk],
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)

        with self.subTest("detail own org"):
            url = reverse(
                "connection_api:batch_command_detail",
                args=[batch_org1.pk],
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_shared_batch_command_hidden_from_non_superuser(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        device_org2 = self._create_device(organization=org2)
        batch = self._create_batch_command(organization=None, devices=[device_org2])
        self.client.logout()
        operator = self._create_operator(organizations=[org])
        operator.user_permissions.add(
            Permission.objects.get(codename="view_batchcommand")
        )
        self.client.force_login(operator)

        with self.subTest("list hides org-wide batch"):
            url = reverse("connection_api:batch_command_list")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 0)

        with self.subTest("detail returns 404 for org-wide batch"):
            url = reverse("connection_api:batch_command_detail", args=[batch.pk])
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)

        with self.subTest("superuser still sees org-wide batch"):
            self.client.logout()
            self._login()
            url = reverse("connection_api:batch_command_list")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 1)

    def test_batch_command_endpoints_unauthorized(self):
        self.client.logout()
        execute_url = reverse("connection_api:batch_command_execute")

        with self.subTest("List"):
            url = reverse("connection_api:batch_command_list")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 401)

        with self.subTest("Detail"):
            url = reverse(
                "connection_api:batch_command_detail",
                args=[uuid.uuid4()],
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 401)

        with self.subTest("Dry run"):
            response = self.client.get(execute_url)
            self.assertEqual(response.status_code, 401)

        with self.subTest("Execute"):
            response = self.client.post(
                execute_url,
                data=json.dumps({"type": "custom"}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 401)

    def test_batch_command_bearer_authentication(self):
        self.client.logout()
        org = self._get_org()
        batch = self._create_batch_command(organization=org)
        device = self._create_device(
            name="bearer-dev",
            mac_address="00:11:22:33:44:be",
            organization=org,
        )
        self._create_config(device=device)
        self._create_device_connection(device=device)
        token = self._obtain_auth_token(username="admin", password="tester")
        auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        with self.subTest("list"):
            url = reverse("connection_api:batch_command_list")
            response = self.client.get(url, **auth)
            self.assertEqual(response.status_code, 200)
            self.assertIn("results", response.data)

        with self.subTest("detail"):
            url = reverse(
                "connection_api:batch_command_detail",
                args=[batch.pk],
            )
            response = self.client.get(url, **auth)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["id"], str(batch.pk))

        with self.subTest("dry-run"):
            url = reverse("connection_api:batch_command_execute")
            response = self.client.get(
                url,
                data={"organization": str(org.pk)},
                **auth,
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("execute"):
            url = reverse("connection_api:batch_command_execute")
            payload = {
                "organization": str(org.pk),
                "type": "custom",
                "input": {"command": "echo test"},
                "label": "test-label",
                "devices": [str(device.pk)],
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
                **auth,
            )
            self.assertEqual(response.status_code, 201)
            self.assertIn("batch", response.data)

    def test_batch_command_detail_404(self):
        org = self._get_org()
        self._create_batch_command(organization=org)
        url = reverse(
            "connection_api:batch_command_detail",
            args=[uuid.uuid4()],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_batch_command_endpoints_operator_different_org(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        batch_org1 = self._create_batch_command(organization=org)
        self.client.logout()
        operator = self._create_operator(organizations=[org2])
        self.client.force_login(operator)

        with self.subTest("list"):
            url = reverse("connection_api:batch_command_list")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 0)

        with self.subTest("detail"):
            url = reverse(
                "connection_api:batch_command_detail",
                args=[batch_org1.pk],
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)

        with self.subTest("dry-run"):
            url = reverse("connection_api:batch_command_execute")
            response = self.client.get(
                url,
                data={"organization": str(org.pk)},
            )
            self.assertEqual(response.status_code, 400)

        with self.subTest("execute"):
            url = reverse("connection_api:batch_command_execute")
            payload = {
                "organization": str(org.pk),
                "type": "custom",
                "input": {"command": "echo test"},
                "label": "test-label",
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)

    def test_batch_command_execute_org_mismatched_data_provided(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        device_org2 = self._create_device(
            name="api-mm-dev",
            mac_address="00:11:22:33:44:88",
            organization=org2,
        )
        url = reverse("connection_api:batch_command_execute")

        with self.subTest("device org mismatch"):
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "test-label",
                        "devices": [str(device_org2.pk)],
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.data,
                {
                    "devices": [
                        "All devices must belong to the same "
                        "organization as the batch command."
                    ]
                },
            )

        with self.subTest("group org mismatch"):
            group_org2 = DeviceGroup.objects.create(
                name="api-mm-group",
                organization=org2,
            )
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "test-label",
                        "group": str(group_org2.pk),
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.data,
                {
                    "group": [
                        (
                            "Please ensure that the organization of this Mass command "
                            "and the organization of the related Device Group match."
                        )
                    ]
                },
            )

        with self.subTest("location org mismatch"):
            location_org2 = Location.objects.create(
                name="api-mm-loc",
                type="indoor",
                organization=org2,
            )
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "test-label",
                        "location": str(location_org2.pk),
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.data,
                {
                    "location": [
                        (
                            "Please ensure that the organization of this Mass command "
                            "and the organization of the related location match."
                        )
                    ]
                },
            )

    def test_batch_command_dry_run_org_mismatched_data_provided(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        device_org2 = self._create_device(
            name="dry-mm-dev",
            mac_address="00:11:22:33:44:78",
            organization=org2,
        )
        base_url = reverse("connection_api:batch_command_execute")

        with self.subTest("device org mismatch"):
            url = "{0}?organization={1}&devices={2}".format(
                base_url,
                str(org.pk),
                str(device_org2.pk),
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.data,
                {
                    "devices": [
                        "All devices must belong to the same "
                        "organization as the batch command."
                    ]
                },
            )

        with self.subTest("group org mismatch"):
            group_org2 = DeviceGroup.objects.create(
                name="dry-mm-group",
                organization=org2,
            )
            url = "{0}?organization={1}&group={2}".format(
                base_url,
                str(org.pk),
                str(group_org2.pk),
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.data,
                {
                    "group": [
                        (
                            "Please ensure that the organization of this Mass command "
                            "and the organization of the related Device Group match."
                        )
                    ]
                },
            )

        with self.subTest("location org mismatch"):
            location_org2 = Location.objects.create(
                name="dry-mm-loc",
                type="indoor",
                organization=org2,
            )
            url = "{0}?organization={1}&location={2}".format(
                base_url,
                str(org.pk),
                str(location_org2.pk),
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.data,
                {
                    "location": [
                        (
                            "Please ensure that the organization of this Mass command "
                            "and the organization of the related location match."
                        )
                    ]
                },
            )


class TestBatchCommandsAPITransaction(
    TestAdminMixin, AuthenticationMixin, TransactionTestCase, CreateConnectionsMixin
):
    url_namespace = "connection_api"

    def setUp(self):
        super().setUp()
        self._login()
        patcher = patch("openwisp_controller.connection.tasks.launch_command.delay")
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_batch_command_execute(self):
        org = self._get_org()
        cred = self._create_credentials(name="exec-cred", organization=org)
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
        url = reverse("connection_api:batch_command_execute")

        with self.subTest("execute with explicit devices"):
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "test-label",
                        "devices": [str(device1.pk)],
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            batch = BatchCommand.objects.get(pk=response.data["batch"])
            command = Command.objects.get(batch_command=batch, device=device1)
            self.assertEqual(command.device.pk, device1.pk)
            self.assertEqual(batch.skipped_devices, {})

        with self.subTest("execute with group"):
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "test-label",
                        "group": str(group.pk),
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            batch = BatchCommand.objects.get(pk=response.data["batch"])
            command = Command.objects.get(batch_command=batch, device=device1)
            self.assertEqual(command.device.pk, device1.pk)
            self.assertEqual(batch.skipped_devices, {})

        with self.subTest("execute with location"):
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "test-label",
                        "location": str(location.pk),
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            batch = BatchCommand.objects.get(pk=response.data["batch"])
            command = Command.objects.get(batch_command=batch, device=device2)
            self.assertEqual(command.device.pk, device2.pk)
            self.assertEqual(batch.skipped_devices, {})

        with self.subTest("execute with group and location"):
            DeviceLocation.objects.create(content_object=device1, location=location)
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "test-label",
                        "group": str(group.pk),
                        "location": str(location.pk),
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            batch = BatchCommand.objects.get(pk=response.data["batch"])
            command = Command.objects.get(batch_command=batch, device=device1)
            self.assertEqual(command.device.pk, device1.pk)
            self.assertEqual(batch.skipped_devices, {})

        with self.subTest("execute org-wide"):
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "test-label",
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            batch = BatchCommand.objects.get(pk=response.data["batch"])

            self.assertEqual(
                Command.objects.filter(batch_command=batch).count(),
                2,
            )
            self.assertEqual(batch.skipped_devices, {})

        with self.subTest("execute with empty devices list"):
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "test-label",
                        "devices": [],
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.data,
                ["No devices match the specified criteria."],
            )

        with self.subTest("execute org-wide for superuser"):
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "test-label",
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            batch = BatchCommand.objects.get(pk=response.data["batch"])
            self.assertEqual(
                Command.objects.filter(batch_command=batch).count(),
                2,
            )
            self.assertEqual(batch.skipped_devices, {})

        with self.subTest("execute with empty label"):
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "",
                        "devices": [str(device1.pk)],
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)

        with self.subTest("execute with label exceeding max_length"):
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "a" * 65,
                        "devices": [str(device1.pk)],
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)

        with self.subTest("execute custom type with empty input"):
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "custom",
                        "input": {},
                        "label": "test-label",
                        "devices": [str(device1.pk)],
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)

        with self.subTest("execute with invalid type"):
            response = self.client.post(
                url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "nonexistent",
                        "input": {"command": "echo test"},
                        "label": "test-label",
                        "devices": [str(device1.pk)],
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)

    def test_batch_command_change_password_input_is_not_exposed(self):
        org = self._get_org()
        cred = self._create_credentials(name="batch-pwd-cred", organization=org)
        device = self._create_device(
            name="batch-pwd-dev",
            mac_address="00:11:22:33:44:91",
            organization=org,
        )
        self._create_config(device=device)
        self._create_device_connection(device=device, credentials=cred)
        password = "SuperSecret123"
        response = self.client.post(
            reverse("connection_api:batch_command_execute"),
            data=json.dumps(
                {
                    "organization": str(org.pk),
                    "type": "change_password",
                    "input": {
                        "password": password,
                        "confirm_password": password,
                    },
                    "label": "change password",
                    "devices": [str(device.pk)],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        batch = BatchCommand.objects.get(pk=response.data["batch"])
        self.assertNotIn(password, json.dumps(batch.input))
        list_response = self.client.get(reverse("connection_api:batch_command_list"))
        self.assertEqual(list_response.status_code, 200)
        self.assertNotIn(password, json.dumps(list_response.data))
        detail_response = self.client.get(
            reverse("connection_api:batch_command_detail", args=[batch.pk])
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertNotIn(password, json.dumps(detail_response.data))

    def test_batch_command_execute_skipped_devices(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
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
        execute_url = reverse("connection_api:batch_command_execute")

        with patch.dict(
            ORGANIZATION_ENABLED_COMMANDS,
            {str(org2.pk): ("reboot",)},
        ):
            payload = {
                "type": "custom",
                "input": {"command": "echo test"},
                "label": "test-label",
                "devices": [str(device_a.pk), str(device_b.pk)],
            }
            response = self.client.post(
                execute_url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            batch = BatchCommand.objects.get(pk=response.data["batch"])

            self.assertIn(str(device_b.pk), batch.skipped_devices)
            self.assertIn(
                '"custom" command is not available for this organization',
                batch.skipped_devices[str(device_b.pk)]["error"],
            )
            command_qs = Command.objects.filter(batch_command=batch)
            self.assertTrue(command_qs.filter(device=device_a).exists())
            self.assertFalse(command_qs.filter(device=device_b).exists())
            url = reverse(
                "connection_api:device_command_list",
                args=[device_a.pk],
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            cmd_data = response.data["results"][0]
            self.assertIn("type", cmd_data)
            self.assertIn("input", cmd_data)

        with self.subTest("superuser cross-org list/detail response"):
            list_resp = self.client.get(
                reverse("connection_api:batch_command_list"),
            )
            self.assertEqual(list_resp.status_code, 200)
            self.assertEqual(
                list_resp.data["results"][0]["device_count"],
                2,
            )
            detail_resp = self.client.get(
                reverse(
                    "connection_api:batch_command_detail",
                    args=[batch.pk],
                ),
            )
            self.assertEqual(detail_resp.status_code, 200)
            self.assertEqual(detail_resp.data["device_count"], 2)
            self.assertEqual(len(detail_resp.data["devices"]), 2)

        with self.subTest("skipped: no credentials"):
            device = self._create_device(
                name="skip-nc-dev",
                mac_address="00:11:22:33:44:a1",
                organization=org,
            )
            self._create_config(device=device)
            response = self.client.post(
                execute_url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "test-label",
                        "devices": [str(device.pk)],
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            batch = BatchCommand.objects.get(pk=response.data["batch"])

            self.assertIn(str(device.pk), batch.skipped_devices)
            self.assertIn(
                "Device has no credentials assigned",
                batch.skipped_devices[str(device.pk)]["error"],
            )
            detail_url = reverse(
                "connection_api:batch_command_detail",
                args=[batch.pk],
            )
            detail_response = self.client.get(detail_url)
            self.assertEqual(detail_response.status_code, 200)
            self.assertIn(str(device.pk), detail_response.data["skipped_devices"])

        with self.subTest("skipped: deactivated device"):
            device = self._create_device(
                name="skip-dd-dev",
                mac_address="00:11:22:33:44:a2",
                organization=org,
            )
            self._create_config(device=device)
            dd_cred = self._create_credentials(
                name="skip-dd-cred",
                organization=org,
            )
            self._create_device_connection(device=device, credentials=dd_cred)
            device.deactivate()
            response = self.client.post(
                execute_url,
                data=json.dumps(
                    {
                        "organization": str(org.pk),
                        "type": "custom",
                        "input": {"command": "echo test"},
                        "label": "test-label",
                        "devices": [str(device.pk)],
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            batch = BatchCommand.objects.get(pk=response.data["batch"])

            self.assertIn(str(device.pk), batch.skipped_devices)
            self.assertIn(
                "Device is deactivated",
                batch.skipped_devices[str(device.pk)]["error"],
            )
            detail_url = reverse(
                "connection_api:batch_command_detail",
                args=[batch.pk],
            )
            detail_response = self.client.get(detail_url)
            self.assertEqual(detail_response.status_code, 200)
            self.assertIn(str(device.pk), detail_response.data["skipped_devices"])
