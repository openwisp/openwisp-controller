from time import sleep
from urllib.parse import quote, urlparse
from uuid import UUID

from channels.testing import ChannelsLiveServerTestCase
from django.apps import apps as django_apps
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls import reverse
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from swapper import load_model

from openwisp_users.migrations import (
    allow_operator_view_organization,
    create_default_groups,
)
from openwisp_utils.tests import SeleniumTestMixin

from ...config import migrations as config_migrations
from ...config.tests.utils import CreateDeviceGroupMixin
from ...geo import migrations as geo_migrations
from ...geo.tests.utils import TestGeoMixin
from .. import migrations as connection_migrations
from .. import settings as app_settings
from ..commands import (
    COMMANDS,
    ORGANIZATION_COMMAND_SCHEMA,
    ORGANIZATION_ENABLED_COMMANDS,
    register_command,
    unregister_command,
)
from .utils import CreateConnectionsMixin, SshServer, _uci_show_command_callable

BatchCommand = load_model("connection", "BatchCommand")
Command = load_model("connection", "Command")
Device = load_model("config", "Device")
Location = load_model("geo", "Location")
DeviceLocation = load_model("geo", "DeviceLocation")
Group = load_model("openwisp_users", "Group")
SCOPED_ORGANIZATION_ID = "11111111-1111-1111-1111-111111111111"
DEFAULT_ORGANIZATION_ID = "22222222-2222-2222-2222-222222222222"


@tag("selenium_tests")
class TestDeviceAdmin(
    CreateConnectionsMixin,
    SeleniumTestMixin,
    StaticLiveServerTestCase,
):
    config_app_label = "config"

    def setUp(self):
        self.admin = self._create_admin(
            username=self.admin_username, password=self.admin_password
        )

    def test_command_widget_on_device(self):
        """
        This test checks that the "Send Command" widget is only visible when
        a device has a DeviceConnection object.
        It also checks sending a "Reboot" command to a device and checks
        that the command is executed successfully.
        """
        org = self._get_org()
        creds = self._create_credentials(organization=org)
        device = self._create_config(organization=org).device
        self.login()
        path = reverse(f"admin:{self.config_app_label}_device_change", args=[device.id])
        self.open(path)
        self.hide_loading_overlay()
        # The "Send Command" widget is not visible on devices which do
        # not have a DeviceConnection object
        self.wait_for_invisibility(By.CSS_SELECTOR, "ul.object-tools a#send-command")
        self._create_device_connection(device=device, credentials=creds)
        self.assertEqual(device.deviceconnection_set.count(), 1)
        self.open(path)
        self.hide_loading_overlay()
        # Send reboot command to the device
        self.find_element(
            by=By.CSS_SELECTOR, value="ul.object-tools a#send-command"
        ).click()
        self.find_element(
            by=By.CSS_SELECTOR, value='button.ow-command-btn[data-command="reboot"]'
        ).click()
        self.find_element(by=By.CSS_SELECTOR, value="#ow-command-confirm-yes").click()
        # Wait for the redirect triggered by command submission to complete.
        # Navigating away immediately can race with the redirect
        sleep(0.3)
        self.open(path)
        self.wait_for_visibility(
            By.CSS_SELECTOR,
            "#tabs-container li.recent.commands",
        )
        self.assertEqual(Command.objects.count(), 1)


@tag("selenium_tests")
class TestBatchCommandAdmin(
    TestGeoMixin,
    CreateDeviceGroupMixin,
    CreateConnectionsMixin,
    SeleniumTestMixin,
    ChannelsLiveServerTestCase,
):
    app_label = "connection"
    config_app_label = "config"
    object_model = Device
    location_model = Location
    object_location_model = DeviceLocation

    @classmethod
    def setUpClass(cls):
        if "uci_show" not in COMMANDS:
            register_command(
                "uci_show",
                {
                    "label": "UCI show",
                    "schema": {
                        "title": "UCI show",
                        "type": "object",
                        "required": ["config"],
                        "properties": {
                            "config": {
                                "type": "string",
                                "title": "Config",
                                "minLength": 1,
                                "pattern": ".",
                            }
                        },
                        "message": "Config cannot be empty.",
                        "additionalProperties": False,
                    },
                    "callable": _uci_show_command_callable,
                },
            )
            cls.addClassCleanup(unregister_command, "uci_show")
        ORGANIZATION_ENABLED_COMMANDS[SCOPED_ORGANIZATION_ID] = (
            "custom",
            "reboot",
            "change_password",
            "uci_show",
        )
        ORGANIZATION_ENABLED_COMMANDS[DEFAULT_ORGANIZATION_ID] = (
            "custom",
            "reboot",
            "change_password",
        )
        for organization_id in (SCOPED_ORGANIZATION_ID, DEFAULT_ORGANIZATION_ID):
            ORGANIZATION_COMMAND_SCHEMA[organization_id] = {
                command: COMMANDS[command]["schema"]
                for command in ORGANIZATION_ENABLED_COMMANDS[organization_id]
            }
            cls.addClassCleanup(
                ORGANIZATION_ENABLED_COMMANDS.pop, organization_id, None
            )
            cls.addClassCleanup(ORGANIZATION_COMMAND_SCHEMA.pop, organization_id, None)
        super().setUpClass()
        cls.mock_ssh_server = SshServer(
            {"root": cls._TEST_RSA_PRIVATE_KEY_PATH}
        ).__enter__()
        cls.addClassCleanup(cls.mock_ssh_server.__exit__)
        cls.ssh_server.port = cls.mock_ssh_server.port

    def setUp(self):
        super().setUp()
        self._restore_default_groups()
        self.execute_url = reverse(f"admin:{self.app_label}_batchcommand_execute")
        self.confirm_url = reverse(f"admin:{self.app_label}_batchcommand_confirm")
        self.changelist_url = reverse(f"admin:{self.app_label}_batchcommand_changelist")

    # this is a TransactionTestCase: the flush performed after every test
    # restores what post_migrate creates (permissions, content types) but
    # not the rows written by data migrations, so the default groups are
    # lost and _create_operator() would return a user without permissions
    def _restore_default_groups(self):
        if Group.objects.filter(name="Operator").exists():
            return
        models_modules = {
            app_config.label: app_config.models_module
            for app_config in django_apps.get_app_configs()
        }
        try:
            for migration in (
                create_default_groups,
                allow_operator_view_organization,
                config_migrations.assign_permissions_to_groups,
                config_migrations.assign_devicegroup_permissions_to_groups,
                geo_migrations.assign_permissions_to_groups,
                connection_migrations.assign_permissions_to_groups,
                connection_migrations.assign_command_permissions_to_groups,
                connection_migrations.assign_batchcommand_permissions_to_groups,
            ):
                migration(django_apps, None)
        finally:
            for app_config in django_apps.get_app_configs():
                app_config.models_module = models_modules[app_config.label]

    def _create_devices(self, organization, count, credentials=None):
        if credentials is None:
            credentials = self._create_credentials(
                organization=organization,
                params={"username": "root", "password": "password", "port": 5555},
            )
        devices = []
        for index in range(count):
            device = self._create_device(
                name=f"device-{index:03d}",
                organization=organization,
                mac_address="00:11:22:33:{:02x}:{:02x}".format(
                    index // 256, index % 256
                ),
            )
            self._create_device_connection(
                device=device,
                credentials=credentials,
                update_strategy=app_settings.UPDATE_STRATEGIES[0][0],
            )
            devices.append(device)
        return devices

    def _select2(self, field_id, text):
        self.find_element(
            by=By.CSS_SELECTOR, value=f"#select2-{field_id}-container"
        ).click()
        self.find_element(
            by=By.CSS_SELECTOR,
            value=".select2-container--open .select2-search__field",
        ).send_keys(text)
        self.find_element(
            by=By.CSS_SELECTOR,
            value=".select2-container--open .select2-results__option--highlighted",
            timeout=5,
        ).click()
        self.wait_for_invisibility(By.CSS_SELECTOR, ".select2-container--open")

    def _fill_wizard(
        self,
        type,
        label,
        organization=None,
        group=None,
        location=None,
        command_input=None,
        open_page=True,
    ):
        if open_page:
            self.open(self.execute_url)
            self._wait_for_url(self.execute_url)
        self.hide_loading_overlay()
        self.web_driver.execute_script(
            "django.jQuery('#id_group, #id_location').val('').trigger('change');"
        )
        self._select2("id_type", type)
        self.assertEqual(
            self.find_element(
                by=By.CSS_SELECTOR, value="#select2-id_type-container"
            ).get_attribute("title"),
            type,
        )
        for field_name, value in (command_input or {}).items():
            field = self.find_element(
                by=By.CSS_SELECTOR,
                value=f"#id_input_jsoneditor [name='root[{field_name}]']",
                timeout=5,
            )
            field.clear()
            field.send_keys(value)
            self.assertEqual(field.get_attribute("value"), value)
        label_field = self.find_element(by=By.ID, value="id_label")
        label_field.clear()
        label_field.send_keys(label)
        self.assertEqual(label_field.get_attribute("value"), label)
        for field_id, target in (
            ("id_organization", organization),
            ("id_group", group),
            ("id_location", location),
        ):
            if target:
                self._select2(field_id, target.name)
                self.assertEqual(
                    self.find_element(
                        by=By.CSS_SELECTOR, value=f"#select2-{field_id}-container"
                    ).get_attribute("title"),
                    target.name,
                )

    def _open_menu_item(self, group_label, item_label):
        self.find_element(
            by=By.CSS_SELECTOR, value=f'.mg-head[aria-label="{group_label}"]'
        ).click()
        self.find_element(
            by=By.CSS_SELECTOR,
            value=f'.menu-group.active a.mg-link[aria-label="{item_label}"]',
            timeout=5,
        ).click()

    def _search(self, query):
        table = self.find_element(by=By.CSS_SELECTOR, value="#result_list")
        search_field = self.find_element(by=By.ID, value="searchbar")
        search_field.clear()
        search_field.send_keys(query)
        search_field.submit()
        WebDriverWait(self.web_driver, 5).until(
            lambda driver: f"q={quote(query)}" in driver.current_url
        )
        WebDriverWait(self.web_driver, 5).until(EC.staleness_of(table))
        self.hide_loading_overlay()

    def _filter_by(self, title, option):
        current_url = self.web_driver.current_url
        tables = self.web_driver.find_elements(By.CSS_SELECTOR, "#result_list")
        slug = title.replace(" ", "-")
        filter_element = self.find_element(
            by=By.CSS_SELECTOR, value=f".ow-filter.{slug}", wait_for="presence"
        )
        self.web_driver.execute_script(
            "arguments[0].click();",
            filter_element.find_element(By.CSS_SELECTOR, ".filter-title"),
        )
        WebDriverWait(self.web_driver, 5).until(
            lambda driver: "ow-active" in filter_element.get_attribute("class")
        )
        self.web_driver.execute_script(
            "arguments[0].click();",
            self.find_element(
                by=By.XPATH,
                value=(
                    "//div[contains(@class, 'ow-filter')]"
                    f"[contains(@class, '{slug}')]"
                    "//div[contains(@class, 'filter-options')]"
                    f"//a[normalize-space()='{option}']"
                ),
                wait_for="presence",
            ),
        )
        apply_filters = self.web_driver.find_elements(By.ID, "ow-apply-filter")
        if apply_filters:
            apply_filters[0].click()
        WebDriverWait(self.web_driver, 5).until(
            lambda driver: driver.current_url != current_url
        )
        if tables:
            WebDriverWait(self.web_driver, 5).until(EC.staleness_of(tables[0]))
        self.hide_loading_overlay()

    def _open_autocomplete_filter(self, param_name):
        self.find_element(
            by=By.XPATH,
            value=(
                f"//div[@id='ow-changelist-filter']//select[@name='{param_name}']"
                "/following-sibling::span[contains(@class, 'select2')]"
            ),
        ).click()
        self.wait_for_invisibility(
            By.CSS_SELECTOR, ".select2-results__option.loading-results"
        )

    def _autocomplete_options(self, param_name):
        self._open_autocomplete_filter(param_name)
        options = [
            option.text
            for option in self.find_elements(
                by=By.CSS_SELECTOR,
                value=".select2-container--open .select2-results__option",
            )
        ]
        self.find_element(by=By.CSS_SELECTOR, value="#content").click()
        return options

    def _filter_by_autocomplete(self, param_name, option):
        current_url = self.web_driver.current_url
        tables = self.web_driver.find_elements(By.CSS_SELECTOR, "#result_list")
        self._open_autocomplete_filter(param_name)
        self.find_element(
            by=By.XPATH,
            value=(
                "//li[contains(@class, 'select2-results__option')]"
                f"[normalize-space()='{option}']"
            ),
        ).click()
        self.find_element(by=By.ID, value="ow-apply-filter").click()
        WebDriverWait(self.web_driver, 5).until(
            lambda driver: driver.current_url != current_url
        )
        if tables:
            WebDriverWait(self.web_driver, 5).until(EC.staleness_of(tables[0]))
        self.hide_loading_overlay()

    def _filter_options(self, title):
        slug = title.replace(" ", "-")
        return [
            option.get_attribute("textContent").strip()
            for option in self.web_driver.find_elements(
                By.CSS_SELECTOR, f".ow-filter.{slug} .filter-options a"
            )
        ]

    def _changelist_labels(self):
        return [
            row.find_element(By.CSS_SELECTOR, "th.field-label").text
            for row in self._rows()
        ]

    def _select_options(self, field_id):
        return [
            option.text
            for option in self.find_elements(
                by=By.CSS_SELECTOR,
                value=f"#{field_id} option",
                wait_for="presence",
            )
            if option.get_attribute("value")
        ]

    def _wait_for_url(self, path, timeout=None):
        WebDriverWait(self.web_driver, timeout or 5).until(
            lambda driver: urlparse(driver.current_url).path == path
        )
        self.assertEqual(urlparse(self.web_driver.current_url).path, path)

    def _wait_for_review_page(self):
        self._wait_for_url(self.confirm_url)
        self.wait_for_visibility(By.CSS_SELECTOR, ".command-summary", timeout=5)

    def _wait_for_batch_result(self, label, status, count):
        batch = BatchCommand.objects.get(label=label)
        self._wait_for_url(
            reverse(f"admin:{self.app_label}_batchcommand_change", args=[batch.pk]),
            # the test env runs celery synchronously,
            # so 50 commands take a while
            timeout=30,
        )
        self.wait_for_visibility(
            By.CSS_SELECTOR, "ul.messagelist li.success", timeout=5
        )
        self.wait_for_visibility(
            By.CSS_SELECTOR,
            f".field-colored_status .command-status.{status}",
            timeout=5,
        )
        WebDriverWait(self.web_driver, 5).until(
            lambda driver: self._command_statuses() == [status] * count
        )

    def _rows(self):
        return self.find_elements(by=By.CSS_SELECTOR, value="#result_list tbody tr")

    def _device_names(self):
        return [
            row.find_element(By.CSS_SELECTOR, "th.field-name").text
            for row in self._rows()
        ]

    def _command_device_names(self):
        return [
            row.find_element(By.CSS_SELECTOR, "td:first-child").text
            for row in self._rows()
        ]

    def _command_statuses(self):
        return [
            row.find_element(By.CSS_SELECTOR, ".command-status").text
            for row in self._rows()
        ]

    def _summary(self):
        summary = {}
        for row in self.find_elements(
            by=By.CSS_SELECTOR, value=".command-summary .form-row"
        ):
            summary[row.find_element(By.TAG_NAME, "label").text] = row.find_element(
                By.CSS_SELECTOR, ".readonly"
            ).text
        return summary

    def test_execute_batch_command(self):
        org1 = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        devices1 = self._create_devices(org1, 5)
        devices2 = self._create_devices(
            org2,
            2,
            credentials=self._create_credentials_with_key(
                organization=org2, port=self.ssh_server.port
            ),
        )
        grouped_device, located_device, *_ = devices1
        group1 = self._create_device_group(name="group1", organization=org1)
        location1 = self._create_location(name="location1", organization=org1)
        group2 = self._create_device_group(name="group2", organization=org2)
        location2 = self._create_location(name="location2", organization=org2)
        grouped_device.group = group1
        grouped_device.full_clean()
        grouped_device.save()
        self._create_object_location(content_object=located_device, location=location1)
        self.login()

        with self.subTest("custom command"):
            self._fill_wizard(
                type="Custom commands",
                label="small-custom",
                organization=org2,
                command_input={"command": "echo test"},
            )
            self.find_element(by=By.ID, value="review-command-btn").click()
            self._wait_for_review_page()
            summary = self._summary()
            self.assertEqual(summary["Type"], "Custom commands")
            self.assertEqual(summary["Command"], "echo test")
            self.assertEqual(summary["Label"], "small-custom")
            self.assertEqual(summary["Targets"], org2.name)
            self.assertEqual(summary["Will run on"], "2 devices")
            self.assertEqual(self._device_names(), [device.name for device in devices2])
            self.find_element(by=By.ID, value="execute-button").click()
            self._wait_for_batch_result("small-custom", "success", 2)
            label = self.find_element(
                by=By.CSS_SELECTOR, value=".field-label .readonly"
            )
            command_type = self.find_element(
                by=By.CSS_SELECTOR, value=".field-type .readonly"
            )
            command_input = self.find_element(
                by=By.CSS_SELECTOR, value=".field-formatted_input .readonly"
            )
            affected_devices = self.find_element(
                by=By.CSS_SELECTOR, value=".field-affected_devices .readonly"
            )
            self.assertEqual(label.text, "small-custom")
            self.assertEqual(command_type.text, "Custom commands")
            self.assertEqual(command_input.text, "echo test")
            self.assertEqual(affected_devices.text, "2")
            self.assertEqual(
                sorted(self._command_device_names()),
                sorted(device.name for device in devices2),
            )
            self.assertEqual(self._command_statuses(), ["success", "success"])

        with self.subTest("reboot"):
            self._fill_wizard(type="Reboot", label="small-reboot", organization=org1)
            self.find_element(by=By.ID, value="review-command-btn").click()
            self._wait_for_review_page()
            summary = self._summary()
            self.assertEqual(summary["Type"], "Reboot")
            self.assertNotIn("Command", summary)
            self.assertEqual(summary["Will run on"], "5 devices")
            self.find_element(by=By.ID, value="execute-button").click()
            self._wait_for_batch_result("small-reboot", "failed", 5)
            command_type = self.find_element(
                by=By.CSS_SELECTOR, value=".field-type .readonly"
            )
            command_input = self.find_element(
                by=By.CSS_SELECTOR, value=".field-formatted_input .readonly"
            )
            affected_devices = self.find_element(
                by=By.CSS_SELECTOR, value=".field-affected_devices .readonly"
            )
            self.assertEqual(command_type.text, "Reboot")
            self.assertEqual(command_input.text, "-")
            self.assertEqual(affected_devices.text, "5")
            self.assertEqual(
                sorted(self._command_device_names()),
                sorted(device.name for device in devices1),
            )
            self.assertEqual(self._command_statuses(), ["failed"] * 5)

        with self.subTest("change password"):
            self._fill_wizard(
                type="Change password",
                label="small-password",
                organization=org1,
                command_input={
                    "password": "tester123",
                    "confirm_password": "tester123",
                },
            )
            self.find_element(by=By.ID, value="review-command-btn").click()
            self._wait_for_review_page()
            summary = self._summary()
            self.assertEqual(summary["Type"], "Change password")
            self.assertNotIn("Command", summary)
            self.find_element(by=By.ID, value="execute-button").click()
            self._wait_for_batch_result("small-password", "failed", 5)
            command_type = self.find_element(
                by=By.CSS_SELECTOR, value=".field-type .readonly"
            )
            command_input = self.find_element(
                by=By.CSS_SELECTOR, value=".field-formatted_input .readonly"
            )
            self.assertEqual(command_type.text, "Change password")
            self.assertEqual(command_input.text, "********")
            self.assertEqual(self._command_statuses(), ["failed"] * 5)

        with self.subTest("device group target"):
            self._fill_wizard(
                type="Reboot",
                label="small-group",
                organization=org1,
                group=group1,
            )
            group_options = self._select_options("id_group")
            self.assertEqual(group_options, [group1.name])
            self.assertNotIn(group2.name, group_options)
            self.find_element(by=By.ID, value="review-command-btn").click()
            self._wait_for_review_page()
            summary = self._summary()
            self.assertEqual(summary["Targets"], f"{org1.name}, {group1.name}")
            self.assertEqual(summary["Will run on"], "1 devices")
            self.assertEqual(self._device_names(), [grouped_device.name])
            self.find_element(by=By.ID, value="execute-button").click()
            self._wait_for_batch_result("small-group", "failed", 1)
            self.assertEqual(self._command_device_names(), [grouped_device.name])
            self.assertEqual(self._command_statuses(), ["failed"])

        with self.subTest("location target"):
            self._fill_wizard(
                type="Reboot",
                label="small-location",
                organization=org1,
                location=location1,
            )
            location_options = self._select_options("id_location")
            self.assertEqual(location_options, [location1.name])
            self.assertNotIn(location2.name, location_options)
            self.find_element(by=By.ID, value="review-command-btn").click()
            self._wait_for_review_page()
            summary = self._summary()
            self.assertEqual(summary["Targets"], f"{org1.name}, {location1.name}")
            self.assertEqual(summary["Will run on"], "1 devices")
            self.assertEqual(self._device_names(), [located_device.name])
            self.find_element(by=By.ID, value="execute-button").click()
            self._wait_for_batch_result("small-location", "failed", 1)
            self.assertEqual(self._command_device_names(), [located_device.name])
            self.assertEqual(self._command_statuses(), ["failed"])

        with self.subTest("excluded devices"):
            self._fill_wizard(type="Reboot", label="small-excluded", organization=org1)
            self.find_element(by=By.ID, value="review-command-btn").click()
            self._wait_for_review_page()
            checkbox = self.find_element(
                by=By.CSS_SELECTOR, value="#result_list tbody .device-checkbox"
            )
            excluded_pk = checkbox.get_attribute("value")
            checkbox.click()
            selected_count = self.find_element(by=By.ID, value="selected-count")
            execute_button = self.find_element(by=By.ID, value="execute-button")
            excluded_field = self.find_element(
                by=By.ID, value="id_excluded", wait_for="presence"
            )
            self.assertEqual(selected_count.text, "4")
            self.assertEqual(execute_button.text, "Execute on 4 devices")
            self.assertEqual(excluded_field.get_attribute("value"), excluded_pk)
            execute_button.click()
            self._wait_for_batch_result("small-excluded", "failed", 4)
            affected_devices = self.find_element(
                by=By.CSS_SELECTOR, value=".field-affected_devices .readonly"
            )
            device_pks = [row.get_attribute("data-device-pk") for row in self._rows()]
            self.assertEqual(affected_devices.text, "4")
            self.assertEqual(self._command_statuses(), ["failed"] * 4)
            self.assertNotIn(excluded_pk, device_pks)

        self.assertEqual(self.get_browser_errors(), [])

    def test_execute_large_batch(self):
        org1 = self._get_org()
        devices = self._create_devices(org1, 50)
        device_names = [device.name for device in devices]
        per_page = 20
        second_page_end = per_page * 2
        first_page = device_names[:per_page]
        second_page = device_names[per_page:second_page_end]
        self.login()
        self._fill_wizard(type="Reboot", label="large-reboot", organization=org1)
        self.find_element(by=By.ID, value="review-command-btn").click()
        self._wait_for_review_page()
        summary = self._summary()
        self.assertEqual(summary["Type"], "Reboot")
        self.assertNotIn("Command", summary)
        self.assertEqual(summary["Label"], "large-reboot")
        self.assertEqual(summary["Targets"], org1.name)
        self.assertEqual(summary["Will run on"], "50 devices")

        with self.subTest("the device table is paginated"):
            selected_count = self.find_element(by=By.ID, value="selected-count")
            paginator = self.find_element(by=By.CSS_SELECTOR, value=".paginator")
            self.assertEqual(selected_count.text, "50")
            self.assertEqual(self._device_names(), first_page)
            self.assertIn("50 devices", paginator.text.lower())

        with self.subTest("select all toggles the devices of the page"):
            select_all = self.find_element(by=By.ID, value="select-all-devices")
            selected_count = self.find_element(by=By.ID, value="selected-count")
            select_all.click()
            self.assertEqual(selected_count.text, "30")
            select_all.click()
            self.assertEqual(selected_count.text, "50")

        with self.subTest("exclusions survive pagination"):
            checkbox = self.find_element(
                by=By.CSS_SELECTOR, value="#result_list tbody .device-checkbox"
            )
            excluded_pk = checkbox.get_attribute("value")
            excluded_name = checkbox.get_attribute("aria-label").replace("Include ", "")
            checkbox.click()
            selected_count = self.find_element(by=By.ID, value="selected-count")
            self.assertEqual(selected_count.text, "49")
            self.open(f"{self.confirm_url}?p=2")
            self._wait_for_url(self.confirm_url)
            self.hide_loading_overlay()
            selected_count = self.find_element(by=By.ID, value="selected-count")
            excluded_field = self.find_element(
                by=By.ID, value="id_excluded", wait_for="presence"
            )
            self.assertEqual(self._device_names(), second_page)
            self.assertEqual(selected_count.text, "49")
            self.assertEqual(excluded_field.get_attribute("value"), excluded_pk)
            self.open(self.confirm_url)
            self._wait_for_url(self.confirm_url)
            self.hide_loading_overlay()
            checkbox = self.find_element(
                by=By.CSS_SELECTOR, value="#result_list tbody .device-checkbox"
            )
            self.assertEqual(checkbox.is_selected(), False)

        with self.subTest("the excluded device is left out of the batch"):
            self.find_element(by=By.ID, value="execute-button").click()
            self._wait_for_batch_result("large-reboot", "failed", 20)
            label = self.find_element(
                by=By.CSS_SELECTOR, value=".field-label .readonly"
            )
            command_type = self.find_element(
                by=By.CSS_SELECTOR, value=".field-type .readonly"
            )
            command_input = self.find_element(
                by=By.CSS_SELECTOR, value=".field-formatted_input .readonly"
            )
            affected_devices = self.find_element(
                by=By.CSS_SELECTOR, value=".field-affected_devices .readonly"
            )
            paginator = self.find_element(by=By.CSS_SELECTOR, value=".paginator")
            device_pks = [row.get_attribute("data-device-pk") for row in self._rows()]
            command_names = self._command_device_names()
            self.assertEqual(label.text, "large-reboot")
            self.assertEqual(command_type.text, "Reboot")
            self.assertEqual(command_input.text, "-")
            self.assertEqual(affected_devices.text, "49")
            self.assertEqual(len(command_names), 20)
            self.assertEqual(paginator.text, "49 commands")
            self.assertEqual(self._command_statuses(), ["failed"] * 20)
            self.assertEqual(
                set(command_names) - {device.name for device in devices}, set()
            )
            self.assertNotIn(excluded_name, command_names)
            self.assertNotIn(excluded_pk, device_pks)

        self.assertEqual(self.get_browser_errors(), [])

    def test_batch_command_organization_isolation_and_permissions(self):
        org1 = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        devices1 = self._create_devices(org1, 2)
        self._create_devices(org2, 2)
        group1 = self._create_device_group(name="group1", organization=org1)
        group2 = self._create_device_group(name="group2", organization=org2)
        location1 = self._create_location(name="location1", organization=org1)
        location2 = self._create_location(name="location2", organization=org2)
        batch1 = self._create_batch_command(organization=org1, label="managed-batch")
        batch2 = self._create_batch_command(organization=org2, label="unmanaged-batch")
        operator = self._create_operator(organizations=[org1])
        self.login(username=operator.username, password="tester")

        with self.subTest("the wizard only offers the managed organization"):
            self.open(self.execute_url)
            self._wait_for_url(self.execute_url)
            self.hide_loading_overlay()
            organization_options = self._select_options("id_organization")
            self.assertEqual(organization_options, [org1.name])
            self.assertNotIn(org2.name, organization_options)

        with self.subTest("targets of other organizations are not offered"):
            self._select2("id_organization", org1.name)
            group_options = self._select_options("id_group")
            location_options = self._select_options("id_location")
            self.assertEqual(group_options, [group1.name])
            self.assertEqual(location_options, [location1.name])
            self.assertNotIn(group2.name, group_options)
            self.assertNotIn(location2.name, location_options)

        with self.subTest("the changelist hides other organizations"):
            self.open(self.changelist_url)
            self._wait_for_url(self.changelist_url)
            self.hide_loading_overlay()
            labels = [
                row.find_element(By.CSS_SELECTOR, "th.field-label").text
                for row in self._rows()
            ]
            self.assertEqual(labels, [batch1.label])
            self.assertNotIn(batch2.label, labels)

        with self.subTest("a batch of another organization cannot be opened"):
            self.open(
                reverse(f"admin:{self.app_label}_batchcommand_change", args=[batch2.pk])
            )
            self._wait_for_url(reverse("admin:index"))

        with self.subTest("only the devices of the managed organization are targeted"):
            self._fill_wizard(type="Reboot", label="isolated-reboot", organization=org1)
            self.find_element(by=By.ID, value="review-command-btn").click()
            self._wait_for_review_page()
            summary = self._summary()
            self.assertEqual(summary["Targets"], org1.name)
            self.assertEqual(summary["Will run on"], "2 devices")
            self.assertEqual(self._device_names(), [device.name for device in devices1])
            self.find_element(by=By.ID, value="execute-button").click()
            self._wait_for_batch_result("isolated-reboot", "failed", 2)
            self.assertEqual(
                sorted(self._command_device_names()),
                sorted(device.name for device in devices1),
            )
            self.assertEqual(self._command_statuses(), ["failed"] * 2)

        with self.subTest("the view permission is not enough to execute"):
            viewer = self._create_operator(
                organizations=[org1], username="viewer", email="viewer@test.com"
            )
            viewer.groups.clear()
            viewer.user_permissions.set(
                Permission.objects.filter(codename="view_batchcommand")
            )
            self.web_driver.delete_all_cookies()
            self.login(username=viewer.username, password="tester")
            self.web_driver.get(f"{self.live_server_url}{self.execute_url}")
            self.assertEqual(
                self.find_element(by=By.TAG_NAME, value="body").text,
                "403 Forbidden",
            )
            self.web_driver.get(f"{self.live_server_url}{self.confirm_url}")
            self.assertEqual(
                self.find_element(by=By.TAG_NAME, value="body").text,
                "403 Forbidden",
            )

    def test_batch_command_menu_search_and_filters(self):
        org1 = self._get_org()
        org2 = self._create_org(name="org2", slug="org2")
        devices = self._create_devices(org1, 50)
        searched_device, grouped_device, located_device, *_ = devices
        self._create_devices(org2, 1)
        group1 = self._create_device_group(name="group1", organization=org1)
        location1 = self._create_location(name="location1", organization=org1)
        grouped_device.group = group1
        grouped_device.full_clean()
        grouped_device.save()
        self._create_object_location(content_object=located_device, location=location1)
        self._create_batch_command(organization=org2, label="org2-batch")
        self._create_batch_command(organization=org1, label="group-batch", group=group1)
        self._create_batch_command(
            organization=org1, label="location-batch", location=location1
        )
        self.login()

        with self.subTest("the wizard is reachable from the menu"):
            self.open(reverse("admin:index"))
            self._open_menu_item("Network Operations", "Mass command execute")
            self._wait_for_url(self.execute_url)

        with self.subTest("the whole flow runs on every device"):
            self._fill_wizard(
                type="Reboot",
                label="menu-reboot",
                organization=org1,
                open_page=False,
            )
            self.find_element(by=By.ID, value="review-command-btn").click()
            self._wait_for_review_page()
            summary = self._summary()
            self.assertEqual(summary["Type"], "Reboot")
            self.assertEqual(summary["Label"], "menu-reboot")
            self.assertEqual(summary["Targets"], org1.name)
            self.assertEqual(summary["Will run on"], "50 devices")
            self.find_element(by=By.ID, value="execute-button").click()
            self._wait_for_batch_result("menu-reboot", "failed", 20)
            affected_devices = self.find_element(
                by=By.CSS_SELECTOR, value=".field-affected_devices .readonly"
            )
            paginator = self.find_element(by=By.CSS_SELECTOR, value=".paginator")
            command_names = self._command_device_names()
            self.assertEqual(affected_devices.text, "50")
            self.assertEqual(paginator.text, "50 commands")
            self.assertEqual(len(command_names), 20)
            self.assertEqual(
                set(command_names) - {device.name for device in devices}, set()
            )
            self.assertEqual(self._command_statuses(), ["failed"] * 20)

        with self.subTest("the changelist is reachable from the menu"):
            self.open(reverse("admin:index"))
            self._open_menu_item("Network Operations", "Mass command admin")
            self._wait_for_url(self.changelist_url)
            self.assertEqual(
                self._changelist_labels(),
                ["menu-reboot", "location-batch", "group-batch", "org2-batch"],
            )

        with self.subTest("the changelist search matches the label"):
            self._search("menu-reboot")
            self.assertEqual(self._changelist_labels(), ["menu-reboot"])
            self._search("no-such-batch")
            self.assertEqual(
                self.find_element(by=By.CSS_SELECTOR, value=".paginator").text,
                "0 Mass commands",
            )
            self.open(self.changelist_url)
            self._wait_for_url(self.changelist_url)

        with self.subTest("the changelist filters narrow the results"):
            self._filter_by("status", "failed")
            self.assertEqual(self._changelist_labels(), ["menu-reboot"])
            self.open(self.changelist_url)
            self._wait_for_url(self.changelist_url)
            self._filter_by("status", "idle")
            self.assertEqual(
                set(self._changelist_labels()),
                {"org2-batch", "group-batch", "location-batch"},
            )
            self.open(self.changelist_url)
            self._wait_for_url(self.changelist_url)
            self._filter_by("type", "Reboot")
            self.assertEqual(self._changelist_labels(), ["menu-reboot"])
            self.open(self.changelist_url)
            self._wait_for_url(self.changelist_url)
            self._filter_by("type", "Custom commands")
            self.assertEqual(
                set(self._changelist_labels()),
                {"org2-batch", "group-batch", "location-batch"},
            )
            self.open(self.changelist_url)
            self._wait_for_url(self.changelist_url)

        with self.subTest("the changelist autocomplete filters narrow the results"):
            self._filter_by_autocomplete("organization", org2.name)
            self.assertEqual(self._changelist_labels(), ["org2-batch"])
            self.open(self.changelist_url)
            self._wait_for_url(self.changelist_url)
            self._filter_by_autocomplete("group_id", group1.name)
            self.assertEqual(self._changelist_labels(), ["group-batch"])
            self.open(self.changelist_url)
            self._wait_for_url(self.changelist_url)
            self._filter_by_autocomplete("location_id", location1.name)
            self.assertEqual(self._changelist_labels(), ["location-batch"])
            self.open(self.changelist_url)
            self._wait_for_url(self.changelist_url)

        with self.subTest("the organization filter offers every organization"):
            self.open(self.changelist_url)
            self._wait_for_url(self.changelist_url)
            organization_options = self._autocomplete_options("organization")
            self.assertIn(org1.name, organization_options)
            self.assertIn(org2.name, organization_options)

        with self.subTest("the batch is opened from the changelist"):
            self.open(self.changelist_url)
            self._wait_for_url(self.changelist_url)
            self.find_element(
                by=By.XPATH,
                value="//table[@id='result_list']//a[normalize-space()='menu-reboot']",
            ).click()
            batch = BatchCommand.objects.get(label="menu-reboot")
            self._wait_for_url(
                reverse(f"admin:{self.app_label}_batchcommand_change", args=[batch.pk])
            )
            self.assertEqual(len(self._rows()), 20)

        with self.subTest("the command table is searchable"):
            self.open(
                reverse(
                    f"admin:{self.app_label}_batchcommand_change",
                    args=[BatchCommand.objects.get(label="menu-reboot").pk],
                )
            )
            self._search(searched_device.name)
            self.assertEqual(self._command_device_names(), [searched_device.name])
            self.assertEqual(self._command_statuses(), ["failed"])
            self._search("no-such-device")
            self.assertEqual(
                self.find_element(
                    by=By.CSS_SELECTOR, value="#result_list .empty-results"
                ).text,
                "No commands found.",
            )

        with self.subTest("the command table is filterable"):
            self.open(
                reverse(
                    f"admin:{self.app_label}_batchcommand_change",
                    args=[BatchCommand.objects.get(label="menu-reboot").pk],
                )
            )
            self._filter_by("status", "failed")
            self.assertEqual(self._command_statuses(), ["failed"] * 20)
            self._filter_by("status", "success")
            self.assertEqual(
                self.find_element(
                    by=By.CSS_SELECTOR, value="#result_list .empty-results"
                ).text,
                "No commands found.",
            )
            self.open(
                reverse(
                    f"admin:{self.app_label}_batchcommand_change",
                    args=[BatchCommand.objects.get(label="menu-reboot").pk],
                )
            )
            self._filter_by("device group", group1.name)
            self.assertEqual(self._command_device_names(), [grouped_device.name])
            self.open(
                reverse(
                    f"admin:{self.app_label}_batchcommand_change",
                    args=[BatchCommand.objects.get(label="menu-reboot").pk],
                )
            )
            self._filter_by("location", location1.name)
            self.assertEqual(self._command_device_names(), [located_device.name])
            self.open(
                reverse(
                    f"admin:{self.app_label}_batchcommand_change",
                    args=[BatchCommand.objects.get(label="menu-reboot").pk],
                )
            )
            self._filter_by("organization", org1.name)
            self.assertEqual(len(self._command_device_names()), 20)

        with self.subTest("the operator only sees the managed organization"):
            operator = self._create_operator(organizations=[org1])
            self.web_driver.delete_all_cookies()
            self.login(username=operator.username, password="tester")
            self.open(self.changelist_url)
            self._wait_for_url(self.changelist_url)
            self.assertEqual(
                self._changelist_labels(),
                ["menu-reboot", "location-batch", "group-batch"],
            )
            organization_options = self._autocomplete_options("organization")
            self.assertIn(org1.name, organization_options)
            self.assertNotIn(org2.name, organization_options)
            self._search("menu-reboot")
            self.assertEqual(self._changelist_labels(), ["menu-reboot"])
            self.open(self.changelist_url)
            self._wait_for_url(self.changelist_url)
            self._filter_by("status", "failed")
            self.assertEqual(self._changelist_labels(), ["menu-reboot"])
            self.open(
                reverse(
                    f"admin:{self.app_label}_batchcommand_change",
                    args=[BatchCommand.objects.get(label="menu-reboot").pk],
                )
            )
            filter_titles = [
                title.text
                for title in self.find_elements(
                    by=By.CSS_SELECTOR, value="#ow-changelist-filter .filter-title h3"
                )
            ]
            self.assertIn("By status", filter_titles)
            self.assertNotIn("By organization", filter_titles)

    def test_organization_scoped_custom_command_type(self):
        org1 = self._create_org(
            name="scoped org", slug="scoped-org", id=UUID(SCOPED_ORGANIZATION_ID)
        )
        org2 = self._create_org(
            name="org2", slug="org2", id=UUID(DEFAULT_ORGANIZATION_ID)
        )
        devices1 = self._create_devices(org1, 2)
        self._create_devices(org2, 1)
        self._create_batch_command(organization=org2, label="org2-batch")
        operator1 = self._create_operator(
            organizations=[org1], username="operator1", email="operator1@test.com"
        )
        operator2 = self._create_operator(
            organizations=[org2], username="operator2", email="operator2@test.com"
        )
        default_types = ["Custom commands", "Reboot", "Change password"]

        with self.subTest("the scoped organization is offered the custom type"):
            self.web_driver.delete_all_cookies()
            self.login(username=operator1.username, password="tester")
            self.open(self.execute_url)
            self._wait_for_url(self.execute_url)
            self.hide_loading_overlay()
            self.assertEqual(
                self._select_options("id_type"), default_types + ["UCI show"]
            )

        with self.subTest("the custom type renders the input of its schema"):
            self._fill_wizard(
                type="UCI show",
                label="uci-show",
                organization=org1,
                command_input={"config": "network"},
            )
            self.find_element(by=By.ID, value="review-command-btn").click()
            self._wait_for_review_page()
            summary = self._summary()
            self.assertEqual(summary["Type"], "UCI show")
            self.assertEqual(summary["Command"], "config: network")
            self.assertEqual(summary["Will run on"], "2 devices")
            self.assertEqual(self._device_names(), [device.name for device in devices1])
            self.find_element(by=By.ID, value="execute-button").click()
            self._wait_for_batch_result("uci-show", "failed", 2)
            command_type = self.find_element(
                by=By.CSS_SELECTOR, value=".field-type .readonly"
            )
            command_input = self.find_element(
                by=By.CSS_SELECTOR, value=".field-formatted_input .readonly"
            )
            self.assertEqual(command_type.text, "UCI show")
            self.assertEqual(command_input.text, "config: network")
            self.assertEqual(self._command_statuses(), ["failed"] * 2)

        with self.subTest("the changelist type filter offers the custom type"):
            self.open(self.changelist_url)
            self._wait_for_url(self.changelist_url)
            self.assertIn("UCI show", self._filter_options("type"))
            self._filter_by("type", "UCI show")
            self.assertEqual(self._changelist_labels(), ["uci-show"])

        with self.subTest("another organization only sees the default types"):
            self.web_driver.delete_all_cookies()
            self.login(username=operator2.username, password="tester")
            self.open(self.execute_url)
            self._wait_for_url(self.execute_url)
            self.hide_loading_overlay()
            self.assertEqual(self._select_options("id_type"), default_types)
            self.open(self.changelist_url)
            self._wait_for_url(self.changelist_url)
            self.assertEqual(self._changelist_labels(), ["org2-batch"])
            self.assertNotIn("UCI show", self._filter_options("type"))
