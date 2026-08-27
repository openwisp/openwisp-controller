import json
from unittest.mock import patch
from uuid import uuid4

from django.contrib import admin
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connection as db_connection
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from swapper import load_model

from openwisp_controller.connection.commands import (
    COMMANDS,
    ORGANIZATION_COMMAND_SCHEMA,
    ORGANIZATION_ENABLED_COMMANDS,
)

from ... import settings as module_settings
from ...config.admin import DeviceAdmin
from ...tests import _get_updated_templates_settings
from ...tests.utils import TestAdminMixin
from ..admin import BatchCommandAdmin, BatchCommandExecutionForm
from ..connectors.ssh import Ssh
from ..filters import GroupFilter, LocationFilter, TypeFilter
from ..widgets import CredentialsSchemaWidget
from .utils import BatchCommandMixin, CreateConnectionsMixin

Template = load_model("config", "Template")
Config = load_model("config", "Config")
Device = load_model("config", "Device")
Credentials = load_model("connection", "Credentials")
DeviceConnection = load_model("connection", "DeviceConnection")
Command = load_model("connection", "Command")
Group = load_model("openwisp_users", "Group")
DeviceGroup = load_model("config", "DeviceGroup")
Location = load_model("geo", "Location")
DeviceLocation = load_model("geo", "DeviceLocation")
BatchCommand = load_model("connection", "BatchCommand")


class TestConnectionAdmin(TestAdminMixin, CreateConnectionsMixin, TestCase):
    config_app_label = "config"
    app_label = "connection"

    def _create_multitenancy_test_env(self):
        org1 = self._create_org(name="test1org")
        org2 = self._create_org(name="test2org")
        inactive = self._create_org(name="inactive-org", is_active=False)
        operator = self._create_operator(organizations=[org1, inactive])
        administrator = self._create_administrator(organizations=[org1, inactive])
        cred1 = self._create_credentials(organization=org1, name="test1cred")
        cred2 = self._create_credentials(organization=org2, name="test2cred")
        cred3 = self._create_credentials(organization=inactive, name="test3cred")
        dc1 = self._create_device_connection(credentials=cred1)
        dc2 = self._create_device_connection(credentials=cred2)
        dc3 = self._create_device_connection(credentials=cred3)
        data = dict(
            cred1=cred1,
            cred2=cred2,
            cred3_inactive=cred3,
            dc1=dc1,
            dc2=dc2,
            dc3_inactive=dc3,
            org1=org1,
            org2=org2,
            inactive=inactive,
            operator=operator,
            administrator=administrator,
        )
        return data

    def test_credentials_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f"admin:{self.app_label}_credentials_changelist"),
            visible=[data["cred1"].name, data["org1"].name],
            hidden=[data["cred2"].name, data["org2"].name, data["cred3_inactive"].name],
            administrator=True,
        )

    def test_credentials_organization_fk_autocomplete_view(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=self._get_autocomplete_view_path(
                self.app_label, "credentials", "organization"
            ),
            visible=[data["org1"].name],
            hidden=[data["org2"].name, data["inactive"]],
            administrator=True,
        )

    def test_connection_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f"admin:{self.app_label}_credentials_changelist"),
            visible=[data["dc1"].credentials.name, data["org1"].name],
            hidden=[
                data["dc2"].credentials.name,
                data["org2"].name,
                data["dc3_inactive"].credentials.name,
            ],
            administrator=True,
        )

    def test_connection_credentials_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f"admin:{self.config_app_label}_device_add"),
            visible=[str(data["cred1"].name) + str(" (SSH)")],
            hidden=[str(data["cred2"].name) + str(" (SSH)"), data["cred3_inactive"]],
            select_widget=True,
        )

    def test_credentials_jsonschema_widget_media(self):
        widget = CredentialsSchemaWidget()
        html = widget.media.render()
        expected_list = [
            "admin/js/jquery.init.js",
            "connection/js/credentials.js",
            "connection/css/credentials.css",
        ]
        for expected in expected_list:
            self.assertIn(expected, html)

    def test_credentials_jsonschema_view(self):
        url = reverse(CredentialsSchemaWidget.schema_view_name)
        self._login()
        response = self.client.get(url)
        ssh_schema = json.dumps(Ssh.schema)
        self.assertIn(ssh_schema, response.content.decode("utf8"))

    def test_admin_menu_groups(self):
        # Test menu group (openwisp-utils menu group) for Credentials model
        self.client.force_login(self._get_admin())
        models = ["credentials"]
        response = self.client.get(reverse("admin:index"))
        for model in models:
            with self.subTest(f"test menu group link for {model} model"):
                url = reverse(f"admin:{self.app_label}_{model}_changelist")
                self.assertContains(response, f' class="mg-link" href="{url}"')


class TestCommandInlines(TestAdminMixin, CreateConnectionsMixin, TestCase):
    config_app_label = "config"

    def setUp(self):
        self.admin = self._get_admin()
        self.client.force_login(self.admin)
        self.device_connection = self._create_device_connection()
        self.device = self.device_connection.device

    def _create_custom_command(self):
        return Command.objects.create(
            type="custom", input={"command": "echo hello"}, device=self.device
        )

    def test_command_inline(self):
        url = reverse(
            f"admin:{self.config_app_label}_device_change", args=(self.device.id,)
        )
        with self.subTest(
            'Test "Recent Commands" not shown for a device without commands'
        ):
            response = self.client.get(url)
            self.assertNotContains(response, "Recent Commands")
        with self.subTest('Test "Recent Commands" shown for a device having commands'):
            self._create_custom_command()
            response = self.client.get(url)
            self.assertContains(response, "Recent Commands")

    def test_command_inline_output_loading_overlay(self):
        url = reverse(
            f"admin:{self.config_app_label}_device_change", args=(self.device.id,)
        )
        self._create_custom_command()
        response = self.client.get(url)
        self.assertContains(
            response, '<div class="loader recent-commands-loader"></div>', html=True
        )

    def test_command_status_highlighting(self):
        """Test that command status is displayed with appropriate CSS classes"""
        url = reverse(
            f"admin:{self.config_app_label}_device_change", args=(self.device.id,)
        )
        command = Command.objects.create(
            type="custom",
            input={"command": "echo hello"},
            device=self.device,
            status="success",
        )
        with self.subTest("Test success status"):
            response = self.client.get(url)
            self.assertContains(
                response,
                '<span class="command-status success">success</span>',
                html=True,
            )
        with self.subTest("Test failed status"):
            command.status = "failed"
            command.save()
            response = self.client.get(url)
            self.assertContains(
                response,
                '<span class="command-status failed">failed</span>',
                html=True,
            )
        with self.subTest("Test in-progress status"):
            command.status = "in-progress"
            command.save()
            response = self.client.get(url)
            self.assertContains(
                response,
                '<span class="command-status in-progress">in progress</span>',
                html=True,
            )

    def test_command_writable_inline(self):
        url = reverse(
            f"admin:{self.config_app_label}_device_change", args=(self.device.id,)
        )
        with self.subTest(
            "Test add command form is present for a device without commands"
        ):
            response = self.client.get(url)
            self.assertContains(response, "id_command_set")
        with self.subTest(
            "Test add command form is present for a device having commands"
        ):
            self._create_custom_command()
            response = self.client.get(url)
            self.assertContains(response, "id_command_set")

    def test_command_writable_inline_without_permission(self):
        """
        This test verifies that the WritableCommandInline is
        not added to DeviceAdmin when the user only has view
        permissions for Command model.
        """
        administrator = self._create_administrator(
            organizations=[self.device.organization]
        )
        administrator_group = Group.objects.get(name="Administrator")
        change_command_perm = Permission.objects.get(codename="change_command")
        administrator_group.permissions.remove(change_command_perm)
        self.client.force_login(administrator)
        path = reverse(
            f"admin:{self.config_app_label}_device_change", args=(self.device.id,)
        )
        response = self.client.get(path)
        self.assertNotContains(response, "id_command_set")

    def test_commands_schema_view(self):
        url = reverse(
            f"admin:{Command._meta.app_label}_{Command._meta.model_name}_schema"
        )
        org = self._get_org()
        org_admin = self._create_administrator([org])
        with patch.dict(ORGANIZATION_ENABLED_COMMANDS, {str(org.id): ("reboot",)}):
            with self.subTest("Test superuser request without organization_id"):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                result = json.loads(response.content)
                self.assertIn("custom", result)
                self.assertIn("change_password", result)
                self.assertIn("reboot", result)
            with self.subTest("Test superuser request with organization_id"):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                result = json.loads(response.content)
                self.assertIn("reboot", result)
            self.client.logout()
            self.client.force_login(org_admin)
            with self.subTest("Test org admin request without organization_id"):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 403)
            with self.subTest("Test org admin request with organization_id"):
                response = self.client.get(url, {"organization_id": str(org.id)})
                self.assertEqual(response.status_code, 200)
                self.assertIn("reboot", result)

    @patch.object(
        module_settings,
        "OPENWISP_CONTROLLER_API_HOST",
        "https://example.com",
    )
    def test_notification_host_setting(self, ctx_processors=[]):
        url = reverse(
            f"admin:{self.config_app_label}_device_change", args=(self.device.id,)
        )
        with override_settings(
            TEMPLATES=_get_updated_templates_settings(ctx_processors)
        ):
            response = self.client.get(url)
            self.assertContains(response, "https://example.com")
            self.assertNotContains(response, "owControllerApiHost = window.location")


class TestBatchCommandAdmin(BatchCommandMixin, TestCase):
    app_label = "connection"
    config_app_label = "config"

    def setUp(self):
        self._create_admin()
        self.execute_url = reverse(f"admin:{self.app_label}_batchcommand_execute")
        self.confirm_url = reverse(f"admin:{self.app_label}_batchcommand_confirm")
        self.changelist_url = reverse(f"admin:{self.app_label}_batchcommand_changelist")
        self.device_changelist_url = reverse(
            f"admin:{self.config_app_label}_device_changelist"
        )

    def test_wizard_permissions_and_tenant_isolation(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        self._create_device(organization=org)
        device2 = self._create_device(
            name="device2", mac_address="00:11:22:33:44:02", organization=org2
        )

        with self.subTest("view permission is not enough"):
            viewer = self._create_operator(
                organizations=[org], username="viewer", email="viewer@test.com"
            )
            viewer.groups.clear()
            viewer.user_permissions.set(
                Permission.objects.filter(codename="view_batchcommand")
            )
            self.client.force_login(viewer)
            self.assertEqual(self.client.get(self.execute_url).status_code, 403)
            self.assertEqual(self.client.get(self.confirm_url).status_code, 403)

        with self.subTest("the operator group can reach the wizard"):
            operator = self._create_operator(organizations=[org])
            self.client.force_login(operator)
            self.assertFalse(
                BatchCommandAdmin(BatchCommand, admin.site).has_add_permission(None)
            )
            self.assertEqual(self.client.get(self.execute_url).status_code, 200)

        with self.subTest("a target is required for non superusers"):
            response = self._post_execute()
            self.assertContains(response, "Please select at least one of")

        with self.subTest("devices of unmanaged organizations are not reachable"):
            wizard = self._start_wizard(organization=str(org.pk))
            wizard["organization_id"] = str(org2.pk)
            session = self.client.session
            session[BatchCommandAdmin.session_key] = wizard
            session.save()
            self.client.get(self.confirm_url)
            response = self._post_confirm(wizard["token"])
            self.assertIn(
                "No devices match the specified criteria.", self._messages(response)
            )
            self.assertFalse(BatchCommand.objects.exists())

        with self.subTest("superusers may target every device"):
            self._login()
            self._start_wizard()
            response = self.client.get(self.confirm_url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["device_count"], 2)
            self.assertIn(device2, response.context["cl"].queryset)

    def test_wizard_incompatible_scopes(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        group2 = DeviceGroup.objects.create(name="group2", organization=org2)
        location2 = Location.objects.create(
            name="location2", type="indoor", organization=org2
        )
        group = DeviceGroup.objects.create(name="group1", organization=org)
        location = Location.objects.create(
            name="location1", type="indoor", organization=org
        )
        device = self._create_device(organization=org, group=group)
        operator = self._create_operator(organizations=[org, org2])
        self.client.force_login(operator)

        with self.subTest("group of another organization"):
            response = self._post_execute(
                organization=str(org.pk), group=str(group2.pk)
            )
            self.assertIn("group", response.context["form"].errors)

        with self.subTest("location of another organization"):
            response = self._post_execute(
                organization=str(org.pk), location=str(location2.pk)
            )
            self.assertIn("location", response.context["form"].errors)

        with self.subTest("the organization is derived from the group"):
            wizard = self._start_wizard(group=str(group.pk))
            self.assertEqual(wizard["group_id"], str(group.pk))
            response = self.client.get(self.confirm_url)
            self.assertEqual(response.context["device_count"], 1)

        with self.subTest("scopes which share no devices"):
            wizard = self._start_wizard(
                organization=str(org.pk),
                group=str(group.pk),
                location=str(location.pk),
            )
            response = self.client.get(self.confirm_url)
            self.assertEqual(response.context["device_count"], 0)
            response = self._post_confirm(wizard["token"])
            self.assertIn(
                "No devices match the specified criteria.", self._messages(response)
            )
            self.assertFalse(BatchCommand.objects.exists())
            self.assertIn(device, Device.objects.all())

    def test_wizard_form_fields(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        group = DeviceGroup.objects.create(name="group1", organization=org)
        group2 = DeviceGroup.objects.create(name="group2", organization=org2)
        location = Location.objects.create(
            name="location1", type="indoor", organization=org
        )
        location2 = Location.objects.create(
            name="location2", type="indoor", organization=org2
        )
        operator = self._create_operator(organizations=[org])
        self.client.force_login(operator)

        with self.subTest("choices are limited to the managed organizations"):
            form = self.client.get(self.execute_url).context["form"]
            self.assertEqual(list(form.fields["organization"].queryset), [org])
            self.assertEqual(list(form.fields["group"].queryset), [group])
            self.assertEqual(list(form.fields["location"].queryset), [location])

        with self.subTest("types are limited to the enabled commands"):
            with patch.dict(ORGANIZATION_ENABLED_COMMANDS, {str(org.pk): ("reboot",)}):
                form = self.client.get(self.execute_url).context["form"]
                choices = form.fields["type"].choices
                self.assertEqual([value for value, _ in choices], ["", "reboot"])

        with self.subTest("superusers are not restricted"):
            self._login()
            form = self.client.get(self.execute_url).context["form"]
            self.assertIn(group2, form.fields["group"].queryset)
            self.assertIn(location2, form.fields["location"].queryset)
            self.assertIn(org2, form.fields["organization"].queryset)

    def test_wizard_schema_view(self):
        org = self._get_org()
        url = reverse(f"admin:{self.app_label}_batchcommand_schema")

        with self.subTest("superusers get every enabled type"):
            self._login()
            schemas = self.client.get(url).json()
            form = self.client.get(self.execute_url).context["form"]
            choices = {value for value, _ in form.fields["type"].choices if value}
            self.assertEqual(set(schemas), choices)

        with self.subTest("superusers get the schemas of every organization"):
            with patch.dict(
                ORGANIZATION_COMMAND_SCHEMA,
                {
                    "__all__": {"reboot": COMMANDS["reboot"]["schema"]},
                    str(org.pk): {
                        "change_password": COMMANDS["change_password"]["schema"]
                    },
                },
                clear=True,
            ):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(sorted(response.json()), ["change_password", "reboot"])

        with self.subTest("superusers do not need an __all__ configuration"):
            with patch.dict(
                ORGANIZATION_COMMAND_SCHEMA,
                {str(org.pk): {"reboot": COMMANDS["reboot"]["schema"]}},
                clear=True,
            ):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(list(response.json()), ["reboot"])

        with self.subTest("an empty configuration returns an empty object"):
            with patch.dict(ORGANIZATION_COMMAND_SCHEMA, {}, clear=True):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {})

        with self.subTest("managers get the union of their organizations"):
            operator = self._create_operator(organizations=[org])
            self.client.force_login(operator)
            with patch.dict(
                ORGANIZATION_COMMAND_SCHEMA,
                {str(org.pk): {"reboot": COMMANDS["reboot"]["schema"]}},
            ):
                self.assertEqual(list(self.client.get(url).json()), ["reboot"])

        with self.subTest("the add permission is required"):
            viewer = self._create_operator(
                organizations=[org], username="viewer", email="viewer@test.com"
            )
            viewer.groups.clear()
            viewer.user_permissions.set(
                Permission.objects.filter(codename="view_batchcommand")
            )
            self.client.force_login(viewer)
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_wizard_organization_guard_survives_a_wider_queryset(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        group2 = DeviceGroup.objects.create(name="group2", organization=org2)
        operator = self._create_operator(organizations=[org])
        self.client.force_login(operator)
        request = self.client.get(self.execute_url).wsgi_request
        form = BatchCommandExecutionForm(
            data={
                "type": "custom",
                "input": '{"command": "echo test"}',
                "label": "test-label",
                "notes": "",
                "organization": "",
                "group": str(group2.pk),
                "location": "",
            },
            request=request,
        )
        form.fields["group"].queryset = DeviceGroup.objects.all()
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["group"], ["Select a valid choice."])

    def test_wizard_views_reject_unsupported_methods(self):
        self._login()
        response = self.client.delete(self.execute_url)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET, POST")
        response = self.client.delete(self.confirm_url)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET, POST")

    def test_wizard_back_restores_the_form(self):
        org = self._get_org()
        group = DeviceGroup.objects.create(name="back-group", organization=org)
        self._create_device(organization=org, group=group)
        self._login()
        self._post_execute(
            type="custom",
            input='{"command": "echo back"}',
            label="back-label",
            notes="back notes",
            organization=str(org.pk),
            group=str(group.pk),
        )
        form = self.client.get(f"{self.execute_url}?back=1").context["form"]
        self.assertEqual(form.initial["type"], "custom")
        self.assertEqual(form.initial["input"], {"command": "echo back"})
        self.assertEqual(form.initial["label"], "back-label")
        self.assertEqual(form.initial["notes"], "back notes")
        self.assertEqual(form.initial["organization"], str(org.pk))
        self.assertEqual(form.initial["group"], str(group.pk))
        self.assertIsNone(form.initial["location"])
        self.assertIn(BatchCommandAdmin.session_key, self.client.session)
        form = self.client.get(self.execute_url).context["form"]
        self.assertEqual(form.initial, {})
        self.assertNotIn(BatchCommandAdmin.session_key, self.client.session)

    def test_wizard_device_admin_composition(self):
        class ReplacementDeviceAdmin(DeviceAdmin):
            change_list_template = "admin/connection/replacement_change_list.html"
            readonly_fields = ["last_ip"]

            def monitoring_status(self, obj):
                return "ok"

            monitoring_status.short_description = "monitoring status"

        model_admin = BatchCommandAdmin(BatchCommand, admin.site)
        device_admin_class = type(admin.site.get_model_admin(Device))
        admin.site.unregister(Device)
        admin.site.register(Device, ReplacementDeviceAdmin)
        try:
            registered_readonly = list(ReplacementDeviceAdmin.readonly_fields)
            device_admin = model_admin.get_device_admin(Device.objects.none())
            model_admin.get_device_admin(Device.objects.none())
            template = model_admin.get_device_changelist_template()
        finally:
            admin.site.unregister(Device)
            admin.site.register(Device, device_admin_class)

        self.assertIsInstance(device_admin, ReplacementDeviceAdmin)
        self.assertTrue(hasattr(device_admin, "monitoring_status"))
        self.assertEqual(template, "admin/connection/replacement_change_list.html")
        self.assertIn("last_ip", device_admin.readonly_fields)
        self.assertEqual(
            list(ReplacementDeviceAdmin.readonly_fields), registered_readonly
        )

        with self.subTest("a registration without a template falls back"):

            class BareDeviceAdmin(DeviceAdmin):
                change_list_template = None

            admin.site.unregister(Device)
            admin.site.register(Device, BareDeviceAdmin)
            try:
                self.assertEqual(
                    model_admin.get_device_changelist_template(),
                    "admin/change_list.html",
                )
            finally:
                admin.site.unregister(Device)
                admin.site.register(Device, device_admin_class)

        self.assertIs(type(admin.site.get_model_admin(Device)), device_admin_class)

    def test_wizard_and_detail_query_budget(self):
        """The pages must not run a query per listed row.

        The absolute count depends on caches which are warm or cold depending
        on what ran before, so the budget asserted here is that listing three
        times as many rows costs exactly the same number of queries.
        """
        org = self._get_org()
        devices = [
            self._create_device(
                name=f"budget{index}",
                mac_address=f"00:11:22:33:55:{index:02x}",
                organization=org,
            )
            for index in range(4)
        ]
        batch = self._create_batch_command(organization=org)
        self._create_commands(batch, devices)
        batch.skipped_devices = {
            str(uuid4()): {"name": "skipped-device", "error": "no credentials"}
        }
        batch.save(update_fields=["skipped_devices"])
        more_devices = [
            self._create_device(
                name=f"budget-more{index}",
                mac_address=f"00:11:22:33:56:{index:02x}",
                organization=org,
            )
            for index in range(8)
        ]
        self._login()

        with self.subTest("the confirm page"):
            self._start_wizard(organization=str(org.pk))
            self.client.get(self.confirm_url)
            with CaptureQueriesContext(db_connection) as few:
                self.client.get(self.confirm_url)
            self._start_wizard(organization=str(org.pk))
            self.client.get(self.confirm_url)
            with CaptureQueriesContext(db_connection) as many:
                response = self.client.get(self.confirm_url)
            self.assertEqual(response.context["device_count"], len(devices) + 8)
            self.assertEqual(len(many.captured_queries), len(few.captured_queries))

        with self.subTest("the detail page"):
            url = reverse(
                f"admin:{self.app_label}_batchcommand_change", args=[batch.pk]
            )
            self.client.get(url)
            with CaptureQueriesContext(db_connection) as few:
                self.client.get(url)
            self._create_commands(batch, more_devices)
            self.client.get(url)
            with CaptureQueriesContext(db_connection) as many:
                response = self.client.get(url)
            self.assertEqual(len(response.context["commands"]), len(devices) + 8 + 1)
            self.assertEqual(len(many.captured_queries), len(few.captured_queries))

    def test_wizard_review_step_input(self):
        model_admin = BatchCommandAdmin(BatchCommand, admin.site)
        cases = (
            (None, ""),
            ("not-a-mapping", ""),
            ({"command": "uptime"}, "uptime"),
            ({"config": "network"}, "config: network"),
            (
                {"service": "firewall", "action": "restart"},
                "service: firewall, action: restart",
            ),
            ({"password": "tester123", "confirm_password": "tester123"}, ""),
            ({"newPassword": "tester123"}, ""),
            ({"Password": "tester123", "host": "10.0.0.1"}, "host: 10.0.0.1"),
        )
        for command_input, expected in cases:
            with self.subTest(str(command_input)):
                self.assertEqual(model_admin._describe_input(command_input), expected)

    def test_wizard_recovers_from_unresolvable_targets(self):
        org = self._get_org()
        self._create_device(organization=org)
        self._login()

        with self.subTest("a confirm page without a wizard restarts"):
            response = self.client.get(self.confirm_url)
            self.assertRedirects(response, self.execute_url)

        with self.subTest("targets which cannot be resolved list no devices"):
            self._start_wizard(organization=str(org.pk))
            with patch.object(
                BatchCommand, "dry_run", side_effect=ValidationError("broken")
            ):
                with self.assertLogs(
                    "openwisp_controller.connection.admin", level="WARNING"
                ) as logs:
                    response = self.client.get(self.confirm_url)
                self.assertEqual(response.context["device_count"], 0)
            self.assertIn(
                "Failed to resolve devices for mass command wizard", logs.output[0]
            )

        with self.subTest("a batch which disappears restarts"):
            wizard = self._start_wizard(organization=str(org.pk))
            self.client.get(self.confirm_url)
            with patch.object(BatchCommand, "execute", side_effect=Device.DoesNotExist):
                with self.assertLogs(
                    "openwisp_controller.connection.admin", level="WARNING"
                ) as logs:
                    response = self._post_confirm(wizard["token"])
            self.assertRedirects(response, self.execute_url)
            self.assertFalse(BatchCommand.objects.exists())
            self.assertIn("Failed to execute mass command wizard", logs.output[0])
            self.assertIn(str(org.pk), logs.output[0])

    def test_wizard_stale_and_parallel_sessions(self):
        org = self._get_org()
        self._create_device(organization=org)
        self._login()
        restart_message = "Please fill in the mass command details to continue."

        with self.subTest("no wizard in the session"):
            response = self._post_confirm("any-token")
            self.assertRedirects(response, self.execute_url)
            self.assertIn(restart_message, self._messages(response))

        with self.subTest("a token from another tab"):
            wizard = self._start_wizard(organization=str(org.pk))
            self.client.get(self.confirm_url)
            response = self._post_confirm("stale-token")
            self.assertRedirects(response, self.execute_url)
            self.assertIn(restart_message, self._messages(response))
            self.assertFalse(BatchCommand.objects.exists())

        with self.subTest("double submit"):
            wizard = self._start_wizard(organization=str(org.pk))
            self.client.get(self.confirm_url)
            self._post_confirm(wizard["token"])
            batch = BatchCommand.objects.get()
            response = self._post_confirm(wizard["token"])
            self.assertRedirects(response, self.execute_url)
            self.assertIn(restart_message, self._messages(response))
            self.assertEqual(list(BatchCommand.objects.all()), [batch])
        BatchCommand.objects.all().delete()

        with self.subTest("the targeted devices changed"):
            wizard = self._start_wizard(organization=str(org.pk))
            self.client.get(self.confirm_url)
            self._create_device(
                name="late-device",
                mac_address="00:11:22:33:44:99",
                organization=org,
            )
            response = self._post_confirm(wizard["token"])
            self.assertRedirects(response, self.confirm_url)
            self.assertIn(
                "The targeted devices changed, please review them again.",
                self._messages(response),
            )
            self.assertFalse(BatchCommand.objects.exists())
            self.assertIn(BatchCommandAdmin.session_key, self.client.session)

    def test_wizard_device_selection(self):
        org = self._get_org()
        devices = [self._create_device(organization=org)]
        devices += [
            self._create_device(
                name=f"device{index}",
                mac_address=f"00:11:22:33:44:0{index}",
                organization=org,
            )
            for index in range(1, 4)
        ]
        self._login()

        with self.subTest("excluded devices are left out"):
            wizard = self._start_wizard(organization=str(org.pk))
            self.client.get(self.confirm_url)
            self._post_confirm(wizard["token"], excluded=str(devices[-1].pk))
            batch = BatchCommand.objects.get()
            self.assertEqual(set(batch.devices.all()), set(devices[:-1]))
        BatchCommand.objects.all().delete()

        with self.subTest("malformed entries are ignored"):
            wizard = self._start_wizard(organization=str(org.pk))
            self.client.get(self.confirm_url)
            self._post_confirm(
                wizard["token"],
                excluded=f",not-a-uuid,,{uuid4()},{devices[0].pk},",
            )
            batch = BatchCommand.objects.get()
            self.assertEqual(set(batch.devices.all()), set(devices[1:]))
        BatchCommand.objects.all().delete()

        with self.subTest("excluding every device"):
            wizard = self._start_wizard(organization=str(org.pk))
            self.client.get(self.confirm_url)
            response = self._post_confirm(
                wizard["token"],
                excluded=",".join(str(device.pk) for device in devices),
            )
            self.assertRedirects(response, self.confirm_url)
            self.assertIn(
                "No devices match the specified criteria.", self._messages(response)
            )
            self.assertFalse(BatchCommand.objects.exists())
            self.assertIn(BatchCommandAdmin.session_key, self.client.session)

    def test_device_action_selection(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        devices = [
            self._create_device(
                name=f"device{index}",
                mac_address=f"00:11:22:33:44:0{index}",
                organization=org,
            )
            for index in range(2)
        ]
        device_org2 = self._create_device(
            name="device-org2", mac_address="00:11:22:33:44:09", organization=org2
        )
        self._login()
        with self.subTest("the selection prefills the form"):
            response = self._post_device_action(devices)
            self.assertEqual(response.status_code, 200)
            form = response.context["form"]
            self.assertEqual(response.context["device_count"], 2)
            self.assertEqual(
                set(form.device_ids), {str(device.pk) for device in devices}
            )
            self.assertEqual(form.fields["devices"].initial, ",".join(form.device_ids))
            self.assertEqual(form.fields["organization"].initial, str(org.pk))
            for field_name in ("organization", "group", "location"):
                self.assertTrue(form.fields[field_name].disabled)
        with self.subTest("the selection is announced and the wider targets hidden"):
            self.assertContains(
                response, "The command will run on the 2 devices you selected."
            )
            self.assertContains(response, 'name="devices"')
            self.assertNotContains(response, 'name="group"')
            self.assertNotContains(response, 'name="location"')
        with self.subTest("devices of different organizations are refused"):
            response = self._post_device_action(devices + [device_org2])
            self.assertRedirects(response, self.device_changelist_url)
            self.assertIn(
                "All devices must belong to the same organization",
                " ".join(self._messages(response)),
            )
        with self.subTest("the selection travels to the review step"):
            response = self._post_execute(devices=self._pk_list(devices))
            self.assertEqual(response.status_code, 302)
            wizard = self.client.session[BatchCommandAdmin.session_key]
            self.assertEqual(
                set(wizard["device_ids"]), {str(device.pk) for device in devices}
            )
            response = self.client.get(self.confirm_url)
            self.assertEqual(response.context["device_count"], 2)
            self.assertEqual(response.context["targets_display"], "2 selected devices")
            self.assertEqual(set(response.context["cl"].queryset), set(devices))
        with self.subTest("only the selected devices are executed"):
            self._post_confirm(wizard["token"])
            batch = BatchCommand.objects.get()
            self.assertEqual(set(batch.devices.all()), set(devices))

    def test_device_action_permissions_and_scope(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        device = self._create_device(organization=org)
        device2 = self._create_device(
            name="device2", mac_address="00:11:22:33:44:02", organization=org2
        )
        device_admin = admin.site._registry[Device]
        request = RequestFactory().get(self.device_changelist_url)
        with self.subTest("the add permission is required"):
            viewer = self._create_operator(
                organizations=[org], username="viewer", email="viewer@test.com"
            )
            viewer.groups.clear()
            viewer.user_permissions.set(
                Permission.objects.filter(codename="view_batchcommand")
            )
            request.user = viewer
            self.assertFalse(device_admin.has_execute_mass_command_permission(request))
            self.assertNotIn("execute_mass_command", device_admin.get_actions(request))
        with self.subTest("the operator group can use the action"):
            operator = self._create_operator(organizations=[org])
            request.user = operator
            self.assertTrue(device_admin.has_execute_mass_command_permission(request))
            self.assertIn("execute_mass_command", device_admin.get_actions(request))
        with self.subTest("devices of unmanaged organizations are dropped"):
            self.client.force_login(operator)
            response = self._post_execute(devices=self._pk_list([device, device2]))
            form = response.context["form"]
            self.assertEqual(form.device_ids, [str(device.pk)])
            self.assertIn(
                "Some of the selected devices are no longer available.",
                form.errors["__all__"],
            )
        with self.subTest("devices which disappeared are dropped"):
            self._login()
            response = self._post_execute(devices=f"{device.pk},{uuid4()}")
            self.assertEqual(response.context["form"].device_ids, [str(device.pk)])
        with self.subTest("mixed organizations are refused by the form"):
            response = self._post_execute(devices=self._pk_list([device, device2]))
            form = response.context["form"]
            self.assertIsNone(form.fields["organization"].initial)
            self.assertIn(
                "All devices must belong to the same organization",
                " ".join(form.errors["__all__"]),
            )

    def test_changelist_multitenancy(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        batch = self._create_batch_command(organization=org)
        batch2 = self._create_batch_command(organization=org2, label="other-label")
        operator = self._create_operator(organizations=[org])
        self.client.force_login(operator)

        with self.subTest("only managed organizations are listed"):
            response = self.client.get(self.changelist_url)
            queryset = response.context["cl"].queryset
            self.assertIn(batch, queryset)
            self.assertNotIn(batch2, queryset)

        with self.subTest("an unmanaged batch cannot be opened"):
            url = reverse(
                f"admin:{self.app_label}_batchcommand_change", args=[batch2.pk]
            )
            self.assertEqual(self.client.get(url).status_code, 302)

        with self.subTest("superusers see every batch"):
            self._login()
            response = self.client.get(self.changelist_url)
            queryset = response.context["cl"].queryset
            self.assertIn(batch, queryset)
            self.assertIn(batch2, queryset)

    def test_changelist_filters_and_search(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        group = DeviceGroup.objects.create(name="group1", organization=org)
        device = self._create_device(organization=org, group=group)
        batch = self._create_batch_command(
            organization=org, group=group, devices=[device]
        )
        batch2 = self._create_batch_command(
            organization=org2,
            label="other-label",
            type="reboot",
            input=None,
            status="success",
        )
        self._login()
        cases = (
            ("status", {"status": "success"}, batch2),
            ("type", {"type": "custom"}, batch),
            ("group", {"group_id": str(group.pk)}, batch),
            ("search by label", {"q": "other-label"}, batch2),
            ("search by device name", {"q": device.name}, batch),
            ("search by group name", {"q": "group1"}, batch),
        )
        for name, params, expected in cases:
            with self.subTest(name):
                response = self.client.get(self.changelist_url, params)
                queryset = response.context["cl"].queryset
                self.assertEqual(list(queryset), [expected])

        with self.subTest("combined filters exclude everything"):
            response = self.client.get(
                self.changelist_url, {"status": "success", "type": "custom"}
            )
            self.assertEqual(response.context["cl"].queryset.count(), 0)

        with self.subTest("affected devices is orderable and not duplicated"):
            response = self.client.get(self.changelist_url, {"o": "5"})
            queryset = response.context["cl"].queryset
            self.assertEqual(set(queryset), {batch, batch2})
            self.assertEqual([item._affected_devices for item in queryset], [0, 0])

    def test_changelist_is_read_only(self):
        batch = self._create_batch_command(organization=self._get_org())
        self._login()
        model_admin = BatchCommandAdmin(BatchCommand, admin.site)
        response = self.client.get(self.changelist_url)

        with self.subTest("no bulk actions"):
            self.assertNotIn(
                "delete_selected", model_admin.get_actions(response.wsgi_request)
            )

        with self.subTest("adding and deleting are disabled"):
            self.assertFalse(model_admin.has_add_permission(response.wsgi_request))
            self.assertFalse(
                model_admin.has_delete_permission(response.wsgi_request, batch)
            )

        with self.subTest("no save buttons on the change page"):
            url = reverse(
                f"admin:{self.app_label}_batchcommand_change", args=[batch.pk]
            )
            response = self.client.get(url)
            self.assertFalse(response.context["show_save"])
            self.assertFalse(response.context["show_save_and_continue"])

    def _create_commands(self, batch, devices, **kwargs):
        commands = []
        for device in devices:
            if not hasattr(device, "config"):
                self._create_config(device=device)
            connection = self._create_device_connection(
                device=device,
                credentials=self._create_credentials(
                    name=f"cred-{device.name}", organization=device.organization
                ),
            )
            with patch.object(Command, "_schedule_command"):
                commands.append(
                    Command.objects.create(
                        batch_command=batch,
                        device=device,
                        connection=connection,
                        type="custom",
                        input={"command": "echo test"},
                        **kwargs,
                    )
                )
        return commands

    def test_change_view_command_rows(self):
        org = self._get_org()
        batch = self._create_batch_command(organization=org)
        devices = [self._create_device(organization=org)] + [
            self._create_device(
                name=f"device{index}",
                mac_address=f"00:11:22:33:44:0{index}",
                organization=org,
            )
            for index in range(1, 4)
        ]
        commands = self._create_commands(batch, devices, output="first\nlast")
        batch.skipped_devices = {
            str(uuid4()): {"name": "skipped-device", "error": "no credentials"}
        }
        batch.skipped_devices.update(
            {
                str(uuid4()): {"name": f"skipped{index}", "error": "no credentials"}
                for index in range(4)
            }
        )
        skipped_names = [skipped["name"] for skipped in batch.skipped_devices.values()]
        batch.save(update_fields=["skipped_devices"])
        self._login()
        url = reverse(f"admin:{self.app_label}_batchcommand_change", args=[batch.pk])
        with patch.object(BatchCommandAdmin, "device_commands_per_page", 3):
            with self.subTest("first page"):
                rows = self.client.get(url).context["commands"]
                self.assertEqual(
                    [row["device_name"] for row in rows],
                    [command.device.name for command in commands[:3]],
                )
                self.assertEqual(rows[0]["output"], "… last")
                self.assertEqual(rows[0]["status_display"], "in progress")
                self.assertFalse(rows[0]["is_skipped"])

            with self.subTest("the page spanning commands and skipped devices"):
                rows = self.client.get(url, {"page": 2}).context["commands"]
                self.assertEqual(
                    [row["is_skipped"] for row in rows], [False, True, True]
                )
                self.assertEqual(
                    [row["device_name"] for row in rows[1:]], skipped_names[:2]
                )

            with self.subTest("a page made of skipped devices only"):
                rows = self.client.get(url, {"page": 3}).context["commands"]
                self.assertEqual([row["is_skipped"] for row in rows], [True] * 3)
                self.assertEqual(
                    [row["device_name"] for row in rows], skipped_names[2:]
                )

            with self.subTest("the unfiltered page does not copy the skipped devices"):
                filters = {
                    "q": "",
                    "status": "",
                    "location_id": "",
                    "group_id": "",
                    "organization_id": "",
                }
                self.assertEqual(
                    batch.filter_skipped_items(filters),
                    batch.skipped_devices.items(),
                )
                filters["q"] = "skipped0"
                self.assertEqual(
                    [
                        skipped["name"]
                        for _pk, skipped in batch.filter_skipped_items(filters)
                    ],
                    ["skipped0"],
                )

            with self.subTest("an unusable page falls back to the first"):
                for page in ("abc", 0, 99):
                    response = self.client.get(url, {"page": page})
                    self.assertEqual(response.context["page_obj"].number, 1)

            with self.subTest("the newest command is last"):
                rows = self.client.get(url, {"page": 2}).context["commands"]
                self.assertEqual(rows[0]["device"], commands[-1].device.pk)

    def test_change_view_filters(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        group = DeviceGroup.objects.create(name="group1", organization=org)
        location = Location.objects.create(
            name="location1", type="indoor", organization=org
        )
        device = self._create_device(organization=org, group=group)
        DeviceLocation.objects.create(content_object=device, location=location)
        batch = self._create_batch_command(organization=org, group=group)
        other_group = DeviceGroup.objects.create(name="skipped-group", organization=org)
        skipped_device = self._create_device(
            name="skipped-device",
            mac_address="00:11:22:33:44:88",
            organization=org,
            group=other_group,
        )
        self._create_commands(batch, [device], status="success")
        transferred_group = DeviceGroup.objects.create(
            name="transferred-group", organization=org2
        )
        transferred_location = Location.objects.create(
            name="transferred-location", type="indoor", organization=org2
        )
        transferred_device = self._create_device(
            name="transferred-device",
            mac_address="00:11:22:33:44:89",
            organization=org2,
            group=transferred_group,
        )
        DeviceLocation.objects.create(
            content_object=transferred_device, location=transferred_location
        )
        batch.skipped_devices = {
            str(skipped_device.pk): {
                "name": skipped_device.name,
                "error": "no credentials",
            },
            str(transferred_device.pk): {
                "name": transferred_device.name,
                "error": "no longer belongs to the organization",
            },
        }
        batch.save(update_fields=["skipped_devices"])
        self._login()
        url = reverse(f"admin:{self.app_label}_batchcommand_change", args=[batch.pk])

        with self.subTest("search matches commands and skipped devices"):
            rows = self.client.get(url, {"q": device.name}).context["commands"]
            self.assertEqual([row["device_name"] for row in rows], [device.name])
            rows = self.client.get(url, {"q": "skipped"}).context["commands"]
            self.assertEqual([row["device_name"] for row in rows], ["skipped-device"])

        with self.subTest("status skipped hides the commands"):
            rows = self.client.get(url, {"status": "skipped"}).context["commands"]
            self.assertEqual([row["is_skipped"] for row in rows], [True, True])

        with self.subTest("status success hides the skipped devices"):
            rows = self.client.get(url, {"status": "success"}).context["commands"]
            self.assertEqual([row["is_skipped"] for row in rows], [False])

        with self.subTest("the all choice clears the only active filter"):
            specs = self.client.get(url, {"status": "success"}).context["filter_specs"]
            self.assertEqual(specs[0].choices[0]["display"], "All")
            self.assertEqual(specs[0].choices[0]["query_string"], "?")

        with self.subTest("groups of skipped devices are offered as filters"):
            response = self.client.get(url)
            titles = {
                str(spec.title): spec for spec in response.context["filter_specs"]
            }
            displays = [
                str(choice["display"]) for choice in titles["device group"].choices
            ]
            self.assertIn(other_group.name, displays)
            self.assertIn(group.name, displays)

        with self.subTest("filtering by a group keeps only its devices"):
            rows = self.client.get(url, {"group_id": str(other_group.pk)}).context[
                "commands"
            ]
            self.assertEqual([row["device_name"] for row in rows], ["skipped-device"])

        with self.subTest("filtering by location"):
            DeviceLocation.objects.create(
                content_object=skipped_device, location=location
            )
            rows = self.client.get(url, {"location_id": str(location.pk)}).context[
                "commands"
            ]
            self.assertEqual(
                sorted(row["device_name"] for row in rows),
                sorted([device.name, "skipped-device"]),
            )

        with self.subTest("filtering by organization"):
            rows = self.client.get(url, {"organization_id": str(org.pk)}).context[
                "commands"
            ]
            self.assertEqual(
                sorted(row["device_name"] for row in rows),
                sorted([device.name, "skipped-device"]),
            )
            rows = self.client.get(url, {"organization_id": str(org2.pk)}).context[
                "commands"
            ]
            self.assertEqual(
                [row["device_name"] for row in rows], [transferred_device.name]
            )

        with self.subTest("the organization filter is for superusers only"):
            operator = self._create_operator(organizations=[org])
            self.client.force_login(operator)
            response = self.client.get(url)
            titles = [str(spec.title) for spec in response.context["filter_specs"]]
            self.assertNotIn("organization", titles)

        with self.subTest("the filters do not offer other organizations"):
            specs = {
                str(spec.title): [str(choice["display"]) for choice in spec.choices]
                for spec in self.client.get(url).context["filter_specs"]
            }
            self.assertNotIn(transferred_group.name, specs["device group"])
            self.assertIn(other_group.name, specs["device group"])
            self.assertNotIn(transferred_location.name, specs["location"])
            self.assertIn(location.name, specs["location"])
            self._login()
            specs = {
                str(spec.title): [str(choice["display"]) for choice in spec.choices]
                for spec in self.client.get(url).context["filter_specs"]
            }
            self.assertIn(transferred_group.name, specs["device group"])
            self.assertIn(transferred_location.name, specs["location"])

        with self.subTest("the search term is not an active filter"):
            response = self.client.get(url, {"q": "anything"})
            self.assertFalse(response.context["has_active_filters"])
            response = self.client.get(url, {"status": "success"})
            self.assertTrue(response.context["has_active_filters"])

    def test_change_view_display_fields(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        batch = self._create_batch_command(organization=org)
        model_admin = BatchCommandAdmin(BatchCommand, admin.site)

        with self.subTest("organization display"):
            self.assertEqual(model_admin.organization_display(batch), org.name)
            shared = self._create_batch_command(organization=None, label="shared")
            self.assertEqual(str(model_admin.organization_display(shared)), "All")

        with self.subTest("colored status"):
            self.assertIn(
                f"command-status {batch.status}", model_admin.colored_status(batch)
            )

        with self.subTest("formatted input"):
            self.assertEqual(model_admin.formatted_input(batch), "echo test")
            empty_batch = self._create_batch_command(
                organization=org, label="empty", type="reboot", input=None
            )
            self.assertEqual(model_admin.formatted_input(empty_batch), "-")
            registered_batch = self._create_batch_command(
                organization=org, label="registered"
            )
            registered_batch.input = {"config": "network"}
            self.assertEqual(
                model_admin.formatted_input(registered_batch), "config: network"
            )
            password_batch = self._create_batch_command(
                organization=org,
                label="password",
                type="change_password",
                input={"password": "tester123", "confirm_password": "tester123"},
            )
            self.assertEqual(model_admin.formatted_input(password_batch), "********")

        with self.subTest("affected devices falls back to the model"):
            self.assertEqual(model_admin.affected_devices(batch), 0)
            batch._affected_devices = 7
            self.assertEqual(model_admin.affected_devices(batch), 7)

        with self.subTest("skipped devices rendering"):
            self.assertEqual(model_admin.display_skipped_devices(batch), "-")
            batch.skipped_devices = {
                str(uuid4()): {"name": f"device{index}", "error": "failed"}
                for index in range(12)
            }
            rendered = model_admin.display_skipped_devices(batch)
            self.assertIn("12", rendered)
            self.assertIn("device0: failed", rendered)
            self.assertIn("…", rendered)

        with self.subTest("commands of unmanaged organizations are hidden"):
            device2 = self._create_device(
                name="device-org2",
                mac_address="00:11:22:33:44:77",
                organization=org2,
            )
            self._create_commands(batch, [device2])
            operator = self._create_operator(organizations=[org])
            request = self.client.get(self.changelist_url).wsgi_request
            request.user = operator
            self.assertEqual(model_admin._get_commands(request, batch).count(), 0)

    def test_changelist_filter_classes(self):
        org = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        group = DeviceGroup.objects.create(name="group1", organization=org)
        location = Location.objects.create(
            name="location1", type="indoor", organization=org
        )
        group2 = DeviceGroup.objects.create(name="group2", organization=org2)
        location2 = Location.objects.create(
            name="location2", type="indoor", organization=org2
        )
        batch = self._create_batch_command(organization=org, group=group)
        batch2 = self._create_batch_command(
            organization=org2, label="other-label", type="reboot", input=None
        )
        model_admin = BatchCommandAdmin(BatchCommand, admin.site)
        operator = self._create_operator(organizations=[org])
        self.client.force_login(operator)
        request = self.client.get(self.changelist_url).wsgi_request

        with self.subTest("type lookups are limited to the managed organizations"):
            type_filter = TypeFilter(request, {}, BatchCommand, model_admin)
            self.assertEqual(
                type_filter.lookups(request, model_admin),
                [("custom", "Custom commands")],
            )

        with self.subTest("type lookups list every type for superusers"):
            self._login()
            admin_request = self.client.get(self.changelist_url).wsgi_request
            type_filter = TypeFilter(admin_request, {}, BatchCommand, model_admin)
            lookups = dict(type_filter.lookups(admin_request, model_admin))
            self.assertEqual(set(lookups), {"custom", "reboot"})

        with self.subTest("type queryset"):
            response = self.client.get(self.changelist_url, {"type": "reboot"})
            self.assertEqual(list(response.context["cl"].queryset), [batch2])
            response = self.client.get(self.changelist_url)
            self.assertEqual(set(response.context["cl"].queryset), {batch, batch2})

        with self.subTest("the parameter names match the change page filters"):
            self.assertEqual(GroupFilter.parameter_name, "group_id")
            self.assertEqual(LocationFilter.parameter_name, "location_id")

        with self.subTest("the filters are on the changelist"):
            self.client.force_login(operator)
            response = self.client.get(self.changelist_url)
            specs = {type(spec) for spec in response.context["cl"].filter_specs}
            self.assertIn(GroupFilter, specs)
            self.assertIn(LocationFilter, specs)

        with self.subTest("related choices are limited to the managed organizations"):
            self._create_administrator(organizations=[org])
            self._test_multitenant_admin(
                url=self._get_autocomplete_view_path(
                    self.app_label, "batchcommand", "group"
                ),
                visible=[group.name],
                hidden=[group2.name],
                administrator=True,
            )
            self._test_multitenant_admin(
                url=self._get_autocomplete_view_path(
                    self.app_label, "batchcommand", "location"
                ),
                visible=[location.name],
                hidden=[location2.name],
                administrator=True,
            )
