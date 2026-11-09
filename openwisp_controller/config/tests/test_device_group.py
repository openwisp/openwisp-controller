from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.test import TestCase
from swapper import load_model

from openwisp_utils.tests import catch_signal

from .. import settings as app_settings
from ..signals import group_templates_changed
from .utils import CreateDeviceGroupMixin, CreateTemplateMixin

Device = load_model("config", "Device")
DeviceGroup = load_model("config", "DeviceGroup")


class TestDeviceGroup(CreateDeviceGroupMixin, CreateTemplateMixin, TestCase):
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

    def test_manage_group_templates_skips_disabled_org(self):
        org = self._get_org()
        template = self._create_template(name="new-template", organization=org)
        device_group = self._create_device_group(organization=org)
        device = Device(
            name="test-device",
            organization=org,
            mac_address="00:11:22:33:44:55",
            group=device_group,
        )
        device.full_clean()
        device.save()
        org.is_active = False
        org.save(update_fields=["is_active"])
        DeviceGroup.manage_group_templates(device_group.pk, [], [template.pk])
        device = Device.objects.get(pk=device.pk)
        self.assertEqual(hasattr(device, "config"), False)
