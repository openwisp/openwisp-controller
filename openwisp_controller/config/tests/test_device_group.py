from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.test import TestCase
from swapper import load_model

from openwisp_utils.tests import catch_signal

from .. import settings as app_settings
from ..signals import group_templates_changed
from .utils import CreateDeviceGroupMixin, CreateDeviceMixin, CreateTemplateMixin

Config = load_model("config", "Config")
Device = load_model("config", "Device")
DeviceGroup = load_model("config", "DeviceGroup")
Template = load_model("config", "Template")


class TestDeviceGroup(
    CreateDeviceMixin, CreateDeviceGroupMixin, CreateTemplateMixin, TestCase
):
    def test_device_group(self):
        self._create_device_group(
            meta_data={"captive_portal_url": "https//example.com"}
        )
        self.assertEqual(DeviceGroup.objects.count(), 1)

    def test_device_group_schema_validation(self):
        device_group_schema = {
            "required": ["captive_portal_url"],
            "properties": {
                "captive_portal_url": {
                    "type": "string",
                    "title": "Captive Portal URL",
                },
            },
            "additionalProperties": True,
        }

        with patch.object(app_settings, "DEVICE_GROUP_SCHEMA", device_group_schema):
            with self.subTest("Test for failing validation"):
                self.assertRaises(ValidationError, self._create_device_group)

            with self.subTest("Test for passing validation"):
                self._create_device_group(
                    meta_data={"captive_portal_url": "https://example.com"}
                )

    def test_device_group_signals(self):
        template = self._create_template()
        with catch_signal(
            group_templates_changed
        ) as group_templates_changed_handler, catch_signal(
            post_save
        ) as post_save_handler:
            dg = self._create_device_group()
            dg.templates.add(template)
            group_templates_changed_handler.assert_not_called()
            post_save_handler.assert_called_with(
                signal=post_save,
                sender=load_model("config", "DeviceGroup"),
                instance=dg,
                created=True,
                update_fields=None,
                raw=False,
                using="default",
            )

    def test_manage_devices_group_templates_no_early_termination(self):
        """
        Regression test: when the first device in the batch has no config
        (because its group has no templates), the loop must continue and
        still apply group templates to the second device.
        """
        org = self._get_org()
        t1 = self._create_template(name="t1")
        # group_with_templates has a template; group_without does not
        group_with_templates = self._create_device_group(
            name="group-with-tpl", organization=org
        )
        group_with_templates.templates.add(t1)
        group_without_templates = self._create_device_group(
            name="group-without-tpl", organization=org
        )
        # device1: belongs to a group without templates → no config created
        device1 = self._create_device(
            name="device-no-config",
            organization=org,
            group=group_without_templates,
            mac_address="00:00:00:00:00:01",
        )
        self.assertFalse(hasattr(device1, "config"))
        # device2: has a config object
        device2 = self._create_device(
            name="device-with-config",
            organization=org,
            mac_address="00:00:00:00:00:02",
        )
        Config.objects.create(
            device=device2,
            backend="netjsonconfig.OpenWrt",
        )
        device2.refresh_from_db()
        self.assertTrue(hasattr(device2, "config"))
        self.assertEqual(device2.config.templates.count(), 0)
        # Call manage_devices_group_templates with device1 (no config) first,
        # then device2 (has config). device1 should be skipped, device2 must
        # still get group_with_templates's template applied.
        Device.manage_devices_group_templates(
            device_ids=[device1.pk, device2.pk],
            old_group_ids=[None, None],
            group_id=group_with_templates.pk,
        )
        device2.refresh_from_db()
        self.assertIn(t1, device2.config.templates.all())
