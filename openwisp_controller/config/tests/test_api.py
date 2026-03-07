from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart
from django.test.testcases import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from swapper import load_model

from openwisp_controller.config.api.serializers import BaseConfigSerializer
from openwisp_controller.tests.utils import TestAdminMixin
from openwisp_users.tests.test_api import AuthenticationMixin
from openwisp_utils.tests import capture_any_output, catch_signal

from .. import settings as app_settings
from ..signals import group_templates_changed
from .utils import (
    CreateConfigTemplateMixin,
    CreateDeviceGroupMixin,
    TestVpnX509Mixin,
    TestWireguardVpnMixin,
)

Template = load_model("config", "Template")
Vpn = load_model("config", "Vpn")
VpnClient = load_model("config", "VpnClient")
Device = load_model("config", "Device")
Config = load_model("config", "Config")
DeviceGroup = load_model("config", "DeviceGroup")
DeviceLocation = load_model("geo", "DeviceLocation")
Location = load_model("geo", "Location")
OrganizationUser = load_model("openwisp_users", "OrganizationUser")


class ApiTestMixin:
    @property
    def _template_data(self):
        return {
            "name": "test-template",
            "organization": None,
            "backend": "netjsonconfig.OpenWrt",
            "config": {"interfaces": [{"name": "eth0", "type": "ethernet"}]},
        }

    @property
    def _vpn_data(self):
        return {
            "name": "vpn-test",
            "host": "vpn.testing.com",
            "organization": None,
            "ca": None,
            "backend": "openwisp_controller.vpn_backends.OpenVpn",
            "config": {
                "openvpn": [
                    {
                        "ca": "ca.pem",
                        "cert": "cert.pem",
                        "dev": "tap0",
                        "dev_type": "tap",
                        "dh": "dh.pem",
                        "key": "key.pem",
                        "mode": "server",
                        "name": "example-vpn",
                        "proto": "udp",
                        "tls_server": True,
                    }
                ]
            },
        }

    @property
    def _device_data(self):
        return {
            "name": "change-test-device",
            "organization": None,
            "mac_address": "00:11:22:33:44:55",
            "config": {
                "backend": "netjsonconfig.OpenWrt",
                "status": "modified",
                "templates": [],
                "context": {"lan_ip": "192.168.1.1"},
                "config": {"interfaces": [{"name": "wlan0", "type": "wireless"}]},
            },
        }

    @property
    def _devicegroup_data(self):
        return {
            "name": "Access Points",
            "description": "Group for APs of default organization",
            "organization": "None",
            "meta_data": {"captive_portal_url": "https://example.com"},
            "context": {"SSID": "OpenWISP"},
            "templates": [],
        }


class TestConfigApi(
    ApiTestMixin,
    TestAdminMixin,
    TestWireguardVpnMixin,
    CreateConfigTemplateMixin,
    TestVpnX509Mixin,
    CreateDeviceGroupMixin,
    AuthenticationMixin,
    TestCase,
):
    def setUp(self):
        super().setUp()
        self._login()

    def test_device_create_with_config_api(self):
        self.assertEqual(Device.objects.count(), 0)
        path = reverse("config_api:device_list")
        data = self._device_data
        org = self._get_org()
        data["organization"] = org.pk
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Device.objects.count(), 1)

    def test_config_serializer_validation(self):
        data = {
            "backend": "netjsonconfig.OpenWrt",
            "templates": [],
            "context": '["test_validation"]',
            "config": "{}",
        }
        device = self._create_device()
        ctx = {"device_id": str(device.pk)}
        config = BaseConfigSerializer(data=data, context=ctx)
        self.assertFalse(config.is_valid())
        self.assertIn("context", config.errors)
        self.assertEqual(
            str(config.errors["context"][0]), "the supplied value is not a JSON object"
        )
        self.assertEqual(len(config.errors.keys()), 1)

    def test_device_create_no_config_api(self):
        self.assertEqual(Device.objects.count(), 0)
        path = reverse("config_api:device_list")
        data = self._device_data
        org = self._get_org()
        data["organization"] = org.pk
        data.pop("config")
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(Config.objects.count(), 0)

    def test_device_create_default_config_values(self):
        self.assertEqual(Device.objects.count(), 0)
        path = reverse("config_api:device_list")
        data = self._device_data
        org = self._get_org()
        data["organization"] = org.pk
        data["config"].update({"context": {}, "config": {}})
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(Config.objects.count(), 0)

    def test_device_create_with_group(self):
        self.assertEqual(Device.objects.count(), 0)
        dg = self._create_device_group()
        template = self._create_template()
        dg.templates.add(template)
        path = reverse("config_api:device_list")
        data = self._device_data
        org = self._get_org()
        data["organization"] = org.pk
        data["group"] = dg.pk
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Device.objects.count(), 1)
        self.assertIn(template, Device.objects.first().config.templates.all())

    def test_device_create_exceeds_org_device_limit(self):
        org = self._get_org()
        org.config_limits.device_limit = 1
        org.config_limits.save()
        self._create_device(
            organization=org, name="test-device", mac_address="11:22:33:44:55:66"
        )
        self.assertEqual(Device.objects.count(), 1)

        path = reverse("config_api:device_list")
        data = self._device_data
        data["organization"] = org.pk
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertIn(
            "The maximum amount of allowed devices has"
            f" been reached for organization {org}.",
            str(r.content),
        )
        self.assertEqual(Device.objects.count(), 1)

    def test_device_create_with_invalid_name_api(self):
        path = reverse("config_api:device_list")
        data = self._device_data
        org = self._get_org()
        data.pop("config")
        data["name"] = "T E S T"
        data["organization"] = org.pk
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Must be either a valid hostname or mac address.", str(r.content))

    # POST request should fail with validation error
    def test_device_post_with_templates_of_different_org(self):
        path = reverse("config_api:device_list")
        data = self._device_data
        org_1 = self._get_org()
        data["organization"] = org_1.pk
        org_2 = self._create_org(name="test org2", slug="test-org2")
        t1 = self._create_template(name="t1-org2", organization=org_2)
        data["config"]["templates"] = [str(t1.pk)]

        def execute_assertions(data):
            response = self.client.post(path, data, content_type="application/json")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                str(response.data["config"][0]),
                "The following templates are owned by organizations "
                f"which do not match the organization of this configuration: {t1.name}",
            )

        execute_assertions(data)

        with self.subTest("test with almost default config values"):
            data["config"].update({"context": {}, "config": {}})
            execute_assertions(data)

    def test_device_create_with_devicegroup(self):
        self.assertEqual(Device.objects.count(), 0)
        path = reverse("config_api:device_list")
        data = self._device_data
        org = self._get_org()
        device_group = self._create_device_group()
        data["organization"] = org.pk
        data["group"] = device_group.pk
        response = self.client.post(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(response.data["group"], device_group.pk)

    def test_device_list_api(self):
        device = self._create_device()
        path = reverse("config_api:device_list")
        with patch.object(
            app_settings, "WHOIS_CONFIGURED", False
        ), self.assertNumQueries(3):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        with self.subTest("device list should show most recent first"):
            org = self._get_org()
            recent = self._create_device(
                name="recent-device-2",
                mac_address="00:00:00:00:00:02",
                organization=org,
            )
            oldest = self._create_device(
                name="oldest-device",
                mac_address="00:00:00:00:00:03",
                organization=org,
            )
            oldest.created = timezone.now() - timedelta(days=2)
            oldest.save(update_fields=["created"])
            path = reverse("config_api:device_list")
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            names = [d["name"] for d in response.data["results"]]
            expected = [recent.name, device.name, oldest.name]
            self.assertEqual(names, expected)

    def test_device_list_api_filter(self):
        org1 = self._create_org()
        d1, _, t1 = self._create_wireguard_vpn_template(organization=org1)
        org2 = self._create_org(name="test org 2")
        dg2 = self._create_device_group(organization=org2)
        d2 = self._create_device(
            name="second.device",
            mac_address="A0:11:B2:33:44:66",
            group=dg2,
            organization=org2,
        )
        t2 = self._create_template(name="t2", organization=org2)
        c2 = self._create_config(device=d2, backend="netjsonconfig.OpenWisp")
        c2.templates.add(t2)
        c2.status = "applied"
        c2.full_clean()
        c2.save()
        path = reverse("config_api:device_list")

        def _assert_device_list_filter(response=None, device=None):
            self.assertEqual(response.status_code, 200)
            data = response.data
            self.assertEqual(data["count"], 1)
            self.assertEqual(len(data["results"][0]), 15)
            self.assertEqual(data["results"][0]["id"], str(device.pk))
            self.assertEqual(data["results"][0]["name"], str(device.name))
            self.assertEqual(data["results"][0]["organization"], device.organization.pk)
            self.assertEqual(
                data["results"][0]["config"]["status"], device.config.status
            )
            self.assertEqual(
                data["results"][0]["config"]["backend"], device.config.backend
            )
            self.assertIn("created", data["results"][0].keys())
            if device.group:
                self.assertEqual(data["results"][0]["group"], device.group.pk)

        with self.subTest("Test filtering by name"):
            r1 = self.client.get(f"{path}?name={d1.name.upper()}")
            _assert_device_list_filter(response=r1, device=d1)
            r2 = self.client.get(f"{path}?name={d1.name[0:3]}")
            _assert_device_list_filter(response=r2, device=d1)

        with self.subTest("Test filtering by mac_address"):
            r1 = self.client.get(f"{path}?mac_address={d2.mac_address.lower()}")
            _assert_device_list_filter(response=r1, device=d2)
            r2 = self.client.get(f"{path}?mac_address={d2.mac_address[0:8]}")
            _assert_device_list_filter(response=r2, device=d2)

        with self.subTest("Test filtering using config backend"):
            r1 = self.client.get(f"{path}?config__backend=netjsonconfig.OpenWrt")
            _assert_device_list_filter(response=r1, device=d1)
            r2 = self.client.get(f"{path}?config__backend=netjsonconfig.OpenWisp")
            _assert_device_list_filter(response=r2, device=d2)

        with self.subTest("Test filtering using config status"):
            r1 = self.client.get(f"{path}?config__status=modified")
            _assert_device_list_filter(response=r1, device=d1)
            r2 = self.client.get(f"{path}?config__status=applied")
            _assert_device_list_filter(response=r2, device=d2)

        with self.subTest("Test filtering using organization id"):
            r1 = self.client.get(f"{path}?organization={org1.pk}")
            _assert_device_list_filter(response=r1, device=d1)
            r2 = self.client.get(f"{path}?organization={org2.pk}")
            _assert_device_list_filter(response=r2, device=d2)

        with self.subTest("Test filtering using organization slug"):
            r1 = self.client.get(f"{path}?organization_slug={org1.slug}")
            _assert_device_list_filter(response=r1, device=d1)
            r2 = self.client.get(f"{path}?organization_slug={org2.slug}")
            _assert_device_list_filter(response=r2, device=d2)

        with self.subTest("Test filtering using config templates"):
            r1 = self.client.get(f"{path}?config__templates={t1.pk}")
            _assert_device_list_filter(response=r1, device=d1)
            r2 = self.client.get(f"{path}?config__templates={t2.pk}")
            _assert_device_list_filter(response=r2, device=d2)

        with self.subTest("Test filtering using config templates invalid uuid"):
            # test with invalid uuid string
            r1 = self.client.get(f"{path}?config__templates={t1.pk}invalid_uuid")
            self.assertEqual(r1.status_code, 400)
            self.assertIn("Invalid UUID format", str(r1.content))
            # test with comma separated uuid's string
            r2 = self.client.get(f"{path}?config__templates={t1.pk},{t2.pk}")
            self.assertEqual(r2.status_code, 400)
            self.assertIn("Invalid UUID format", str(r2.content))

        with self.subTest("Test filtering using device groups"):
            r2 = self.client.get(f"{path}?group={dg2.pk}")
            _assert_device_list_filter(response=r2, device=d2)

        with self.subTest("Test filtering using device created"):
            r1 = self.client.get(path, {"created": d1.created})
            _assert_device_list_filter(response=r1, device=d1)
            r2 = self.client.get(path, {"created__gte": d2.created})
            _assert_device_list_filter(response=r2, device=d2)
            r2 = self.client.get(path, {"created__lt": d2.created})
            _assert_device_list_filter(response=r2, device=d1)

    def test_device_filter_templates(self):
        org1 = self._create_org(name="org1")
        org2 = self._create_org(name="org2")
        test_user = self._create_operator(organizations=[org1])
        self.client.force_login(test_user)
        self._create_template(name="t0", organization=None)
        self._create_template(name="t1", organization=org1)
        self._create_template(name="t11", organization=org1)
        self._create_template(name="t2", organization=org2)
        path = reverse("config_api:device_list")
        r = self.client.get(path, {"format": "api"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "t0</option>")
        self.assertContains(r, "t1</option>")
        self.assertContains(r, "t11</option>")
        self.assertNotContains(r, "t2</option>")

    # Device detail having no config
    def test_device_detail_api(self):
        d1 = self._create_device()
        path = reverse("config_api:device_detail", args=[d1.pk])
        with patch.object(
            app_settings, "WHOIS_CONFIGURED", False
        ), self.assertNumQueries(2):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["config"], None)

    # Device detail having config
    def test_device_detail_config_api(self):
        d1 = self._create_device()
        self._create_config(device=d1)
        path = reverse("config_api:device_detail", args=[d1.pk])
        with patch.object(
            app_settings, "WHOIS_CONFIGURED", False
        ), self.assertNumQueries(3):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(r.data["config"], None)

    def test_device_put_api(self):
        d1 = self._create_device(name="test-device")
        self._create_config(device=d1)
        path = reverse("config_api:device_detail", args=[d1.pk])
        org = self._get_org()
        data = {
            "name": "change-test-device",
            "organization": org.pk,
            "mac_address": d1.mac_address,
            "config": {
                "backend": "netjsonconfig.OpenWisp",
                "status": "modified",
                "templates": [],
                "context": "{}",
                "config": "{}",
            },
        }
        r = self.client.put(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "change-test-device")
        self.assertEqual(r.data["organization"], org.pk)
        self.assertEqual(r.data["config"]["backend"], "netjsonconfig.OpenWisp")
        d1.refresh_from_db()
        self.assertEqual(d1.name, "change-test-device")
        self.assertEqual(d1.organization, org)
        self.assertEqual(d1.config.backend, "netjsonconfig.OpenWisp")

    def test_device_put_api_with_default_config_values(self):
        device = self._create_device(name="test-device")
        path = reverse("config_api:device_detail", args=[device.pk])
        org = self._get_org()
        data = {
            "name": "change-test-device",
            "organization": org.pk,
            "mac_address": device.mac_address,
            "config.backend": app_settings.DEFAULT_BACKEND,
            "config.templates": [],
            "config.context": "null",
            "config.config": "null",
        }
        self.assertEqual(Config.objects.count(), 0)
        response = self.client.put(
            path, encode_multipart(BOUNDARY, data), content_type=MULTIPART_CONTENT
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "change-test-device")
        self.assertEqual(response.data["organization"], org.pk)
        device.refresh_from_db()
        self.assertEqual(device.name, "change-test-device")
        self.assertEqual(device.organization, org)
        self.assertEqual(Config.objects.count(), 0)

    def test_device_api_change_config_backend(self):
        t1 = self._create_template(name="t1", backend="netjsonconfig.OpenWrt")
        t2 = self._create_template(name="t2", backend="netjsonconfig.OpenWisp")
        dg1 = self._create_device_group(name="dg-1")
        dg1.templates.add(t1, t2)
        d1 = self._create_device(name="test-device", group=dg1)
        self.assertIn(t1, d1.config.templates.all())
        path = reverse("config_api:device_detail", args=[d1.pk])
        data = {
            "name": "change-test-device",
            "organization": d1.organization.pk,
            "mac_address": d1.mac_address,
            "group": dg1.pk,
            "config": {
                "backend": "netjsonconfig.OpenWisp",
                "status": "modified",
                "templates": [],
                "context": {},
                "config": {},
            },
        }
        r = self.client.put(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["group"], dg1.pk)
        self.assertEqual(r.data["config"]["backend"], "netjsonconfig.OpenWisp")
        self.assertNotIn(t1, d1.config.templates.all())
        self.assertIn(t2, d1.config.templates.all())

    def test_device_patch_with_templates_of_different_org(self):
        org1 = self._create_org(name="testorg")
        d1 = self._create_device(name="org1-config", organization=org1)
        self._create_config(device=d1)
        self.assertEqual(d1.config.templates.count(), 0)
        path = reverse("config_api:device_detail", args=[d1.pk])
        t1 = self._create_template(name="t1", organization=None)
        t2 = self._create_template(name="t2", organization=org1)
        t3 = self._create_template(
            name="t3", organization=self._create_org(name="org2")
        )
        data = {"config": {"templates": [str(t1.id), str(t2.id), str(t3.id)]}}

        response = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            str(response.data["config"][0]),
            "The following templates are owned by organizations which"
            f" do not match the organization of this configuration: {t3}",
        )

    def test_device_change_organization_required_templates(self):
        org1 = self._create_org(name="org1")
        org2 = self._create_org(name="org2")
        org1_template = self._create_template(
            name="org1-template", organization=org1, required=True
        )
        org2_template = self._create_template(
            name="org2-template", organization=org2, required=True
        )
        device = self._create_device(organization=org1)
        config = self._create_config(device=device)
        self.assertEqual(config.templates.count(), 1)
        self.assertEqual(config.templates.first(), org1_template)

        path = reverse("config_api:device_detail", args=[device.pk])
        data = {"organization": org2.pk}
        response = self.client.patch(path, data=data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        device.refresh_from_db()
        config.refresh_from_db()
        self.assertEqual(device.organization, org2)
        self.assertEqual(config.templates.count(), 1)
        self.assertEqual(config.templates.first(), org2_template)

    def test_device_patch_api(self):
        d1 = self._create_device(name="test-device")
        path = reverse("config_api:device_detail", args=[d1.pk])
        data = dict(name="change-test-device")
        r = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "change-test-device")

    def test_device_download_api(self):
        d1 = self._create_device()
        self._create_config(device=d1)
        path = reverse("config_api:download_device_config", args=[d1.pk])
        with self.assertNumQueries(7):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    def test_update_deactivated_device(self):
        device = self._create_device(_is_deactivated=True)
        path = reverse("config_api:device_detail", args=[device.pk])
        data = {"notes": "test"}
        response = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 403)
        response = self.client.put(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_device_deactivate_api(self):
        device = self._create_device()
        path = reverse("config_api:device_deactivate", args=[device.pk])
        response = self.client.post(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["is_deactivated"], True)
        device.refresh_from_db()
        self.assertEqual(device.is_deactivated(), True)

    def test_device_activate_api(self):
        device = self._create_device(_is_deactivated=True)
        path = reverse("config_api:device_activate", args=[device.pk])
        response = self.client.post(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["is_deactivated"], False)
        device.refresh_from_db()
        self.assertEqual(device.is_deactivated(), False)

    def test_device_delete_api(self):
        self._create_template(required=True)
        device = self._create_device()
        config = self._create_config(device=device)
        path = reverse("config_api:device_detail", args=[device.pk])

        with self.subTest("Test deleting device without deactivating"):
            response = self.client.delete(path)
            self.assertEqual(response.status_code, 403)

        device.deactivate()
        device.refresh_from_db()
        config.refresh_from_db()

        with self.subTest("Test deleting device with config in deactivating state"):
            self.assertEqual(device.is_deactivated(), True)
            self.assertEqual(config.is_deactivating(), True)
            response = self.client.delete(path)
            self.assertEqual(response.status_code, 403)

        config.set_status_deactivated()
        config.refresh_from_db()

        with self.subTest("Test deleting device with config in deactivated state"):
            self.assertEqual(device.is_deactivated(), True)
            self.assertEqual(config.is_deactivated(), True)
            response = self.client.delete(path)
            self.assertEqual(response.status_code, 204)
            self.assertEqual(Device.objects.count(), 0)

    def test_deactivating_device_force_deletion(self):
        self._create_template(required=True)
        device = self._create_device()
        config = self._create_config(device=device)
        device.deactivate()
        path = reverse("config_api:device_detail", args=[device.pk])

        with self.subTest(
            "Test force deleting device with config in deactivating state"
        ):
            self.assertEqual(device.is_deactivated(), True)
            self.assertEqual(config.is_deactivating(), True)
            response = self.client.delete(f"{path}?force=true")
            self.assertEqual(response.status_code, 204)
            self.assertEqual(Device.objects.count(), 0)

    def test_template_create_no_org_api(self):
        initial_count = Template.objects.count()
        path = reverse("config_api:template_list")
        data = self._template_data
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(Template.objects.count(), initial_count + 1)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["organization"], None)

    def test_template_create_vpn_with_type_as_generic(self):
        path = reverse("config_api:template_list")
        test_user = self._create_operator(organizations=[self._get_org()])
        self.client.force_login(test_user)
        vpn1 = self._create_vpn(name="vpn1", organization=self._get_org())
        data = self._template_data
        data["organization"] = self._get_org().pk
        data["type"] = "generic"
        data["vpn"] = vpn1.id
        r = self.client.post(path, data, content_type="application/json")
        validation_msg = "To select a VPN, set the template type to 'VPN-client'"
        self.assertIn(validation_msg, r.data["vpn"])
        self.assertEqual(r.status_code, 400)

    def test_template_create_api(self):
        initial_count = Template.objects.count()
        org = self._get_org()
        path = reverse("config_api:template_list")
        data = self._template_data
        data["organization"] = org.pk
        data["required"] = True
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(Template.objects.count(), initial_count + 1)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["organization"], org.pk)

    def test_template_create_of_vpn_type(self):
        org = self._get_org()
        vpn1 = self._create_vpn(name="vpn1", organization=org)
        path = reverse("config_api:template_list")
        data = self._template_data
        data["type"] = "vpn"
        data["vpn"] = vpn1.id
        data["organization"] = org.pk
        initial_count = Template.objects.count()
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(Template.objects.count(), initial_count + 1)
        self.assertEqual(r.status_code, 201)

    def test_template_create_with_shared_vpn(self):
        org1 = self._get_org()
        test_user = self._create_operator(organizations=[org1])
        self.client.force_login(test_user)
        vpn1 = self._create_vpn(name="vpn1", organization=None)
        path = reverse("config_api:template_list")
        data = self._template_data
        data["type"] = "vpn"
        data["vpn"] = vpn1.id
        data["organization"] = org1.pk
        initial_count = Template.objects.count()
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Template.objects.count(), initial_count + 1)
        self.assertEqual(r.data["vpn"], vpn1.id)

    def test_template_creation_with_no_org_by_operator(self):
        path = reverse("config_api:template_list")
        data = self._template_data
        test_user = self._create_operator(organizations=[self._get_org()])
        self.client.force_login(test_user)
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("This field may not be null.", str(r.content))

    def test_template_create_with_empty_config(self):
        path = reverse("config_api:template_list")
        data = self._template_data
        data["config"] = {}
        data["organization"] = self._get_org().pk
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("The configuration field cannot be empty.", str(r.content))

    def test_template_list_api(self):
        org1 = self._get_org()
        initial_count = Template.objects.count()
        self._create_template(name="t1", organization=org1)
        path = reverse("config_api:template_list")
        with self.assertNumQueries(4):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Template.objects.count(), initial_count + 1)

    def test_template_list_api_filter(self):
        org1 = self._create_org()
        _, _, t1 = self._create_wireguard_vpn_template(organization=org1)
        org2 = self._create_org(name="test org 2")
        t2 = self._create_template(
            name="t2",
            organization=org2,
            backend="netjsonconfig.OpenWisp",
            default=True,
            required=True,
        )
        path = reverse("config_api:template_list")

        def _assert_template_list_filter(response=None, template=None):
            self.assertEqual(response.status_code, 200)
            data = response.data
            self.assertEqual(data["count"], 1)
            self.assertEqual(len(data["results"][0]), 13)
            self.assertEqual(data["results"][0]["id"], str(template.pk))
            self.assertEqual(data["results"][0]["name"], str(template.name))
            self.assertEqual(
                data["results"][0]["organization"], template.organization.pk
            )
            self.assertEqual(data["results"][0]["type"], template.type)
            self.assertEqual(data["results"][0]["backend"], template.backend)
            self.assertEqual(data["results"][0]["default"], template.default)
            self.assertEqual(data["results"][0]["required"], template.required)
            if template.vpn:
                self.assertEqual(data["results"][0]["vpn"], template.vpn.pk)

        with self.subTest("Test filtering using organization id"):
            r1 = self.client.get(f"{path}?organization={org1.pk}")
            _assert_template_list_filter(response=r1, template=t1)
            r2 = self.client.get(f"{path}?organization={org2.pk}")
            _assert_template_list_filter(response=r2, template=t2)

        with self.subTest("Test filtering using organization slug"):
            r1 = self.client.get(f"{path}?organization_slug={org1.slug}")
            _assert_template_list_filter(response=r1, template=t1)
            r2 = self.client.get(f"{path}?organization_slug={org2.slug}")
            _assert_template_list_filter(response=r2, template=t2)

        with self.subTest("Test filtering using template backend"):
            r1 = self.client.get(f"{path}?backend=netjsonconfig.OpenWrt")
            _assert_template_list_filter(response=r1, template=t1)
            r2 = self.client.get(f"{path}?backend=netjsonconfig.OpenWisp")
            _assert_template_list_filter(response=r2, template=t2)

        with self.subTest("Test filtering using template type"):
            r1 = self.client.get(f"{path}?type=vpn")
            _assert_template_list_filter(response=r1, template=t1)
            r2 = self.client.get(f"{path}?type=generic")
            _assert_template_list_filter(response=r2, template=t2)

        with self.subTest("Test filtering using template default"):
            r1 = self.client.get(f"{path}?default=false")
            _assert_template_list_filter(response=r1, template=t1)
            r2 = self.client.get(f"{path}?default=true")
            _assert_template_list_filter(response=r2, template=t2)

        with self.subTest("Test filtering using template required"):
            r1 = self.client.get(f"{path}?required=false")
            _assert_template_list_filter(response=r1, template=t1)
            r2 = self.client.get(f"{path}?required=true")
            _assert_template_list_filter(response=r2, template=t2)

        with self.subTest("Test filtering using template created"):
            r1 = self.client.get(path, {"created": t1.created})
            _assert_template_list_filter(response=r1, template=t1)
            r2 = self.client.get(path, {"created__gte": t2.created})
            _assert_template_list_filter(response=r2, template=t2)
            r2 = self.client.get(path, {"created__lt": t2.created})
            _assert_template_list_filter(response=r2, template=t1)

    def test_template_list_for_shared_objects(self):
        org1 = self._get_org()
        self._create_vpn(name="shared-vpn", organization=None)
        test_user = self._create_operator(organizations=[org1])
        self.client.force_login(test_user)
        path = reverse("config_api:template_list")
        r = self.client.get(path, {"format": "api"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "shared-vpn</option>")

    # template-detail having no Org
    def test_template_detail_api(self):
        t1 = self._create_template(name="t1")
        path = reverse("config_api:template_detail", args=[t1.pk])
        with self.assertNumQueries(3):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["organization"], None)

    def test_template_put_api(self):
        t1 = self._create_template(name="t1", organization=None)
        path = reverse("config_api:template_detail", args=[t1.pk])
        org = self._get_org()
        data = {
            "name": "New t1",
            "required": True,
            "organization": org.pk,
            "backend": "netjsonconfig.OpenWrt",
            "config": {"interfaces": [{"name": "eth0", "type": "ethernet"}]},
        }
        r = self.client.put(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "New t1")
        self.assertEqual(r.data["organization"], org.pk)
        self.assertEqual(r.data["required"], True)

    def test_template_patch_api(self):
        t1 = self._create_template(name="t1")
        path = reverse("config_api:template_detail", args=[t1.pk])
        data = dict(name="New t1")
        r = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "New t1")

    def test_template_download_api(self):
        t1 = self._create_template(name="t1")
        path = reverse("config_api:download_template_config", args=[t1.pk])
        with self.assertNumQueries(2):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    def test_template_delete_api(self):
        initial_count = Template.objects.count()
        t1 = self._create_template(name="t1")
        path = reverse("config_api:template_detail", args=[t1.pk])
        r = self.client.delete(path)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Template.objects.count(), initial_count)

    def test_vpn_create_api(self):
        self.assertEqual(Vpn.objects.count(), 0)
        path = reverse("config_api:vpn_list")
        ca1 = self._create_ca()
        data = self._vpn_data
        data["ca"] = ca1.pk
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Vpn.objects.count(), 1)

    def test_vpn_create_with_shared_objects(self):
        org1 = self._get_org()
        shared_ca = self._create_ca(name="shared_ca", organization=None)
        test_user = self._create_administrator(organizations=[org1])
        self.client.force_login(test_user)
        data = self._vpn_data
        data["organization"] = org1.pk
        data["ca"] = shared_ca.pk
        path = reverse("config_api:vpn_list")
        r = self.client.post(path, data, content_type="application/json")
        self.assertEqual(Vpn.objects.count(), 1)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["ca"], shared_ca.pk)

    def test_vpn_list_api(self):
        org = self._get_org()
        self._create_vpn(organization=org)
        path = reverse("config_api:vpn_list")
        with self.assertNumQueries(3):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    def test_vpn_list_api_filter(self):
        org1 = self._create_org()
        org2 = self._create_org(name="test org 2")
        vpn1 = self._create_vpn(organization=org1)
        vpn2 = self._create_wireguard_vpn(organization=org2)
        path = reverse("config_api:vpn_list")

        def _assert_vpn_list_filter(response=None, vpn=None):
            self.assertEqual(response.status_code, 200)
            data = response.data
            self.assertEqual(data["count"], 1)
            self.assertEqual(len(data["results"][0]), 13)
            self.assertEqual(data["results"][0]["id"], str(vpn.pk))
            self.assertEqual(data["results"][0]["name"], str(vpn.name))
            self.assertEqual(data["results"][0]["organization"], vpn.organization.pk)

        with self.subTest("Test filtering using VPN backend"):
            r1 = self.client.get(
                f"{path}?backend=openwisp_controller.vpn_backends.OpenVpn"
            )
            _assert_vpn_list_filter(response=r1, vpn=vpn1)
            r2 = self.client.get(
                f"{path}?backend=openwisp_controller.vpn_backends.Wireguard"
            )
            _assert_vpn_list_filter(response=r2, vpn=vpn2)

        with self.subTest("Test filtering using VPN subnet"):
            r2 = self.client.get(f"{path}?subnet={vpn2.subnet.pk}")
            _assert_vpn_list_filter(response=r2, vpn=vpn2)

        with self.subTest("Test filtering using organization id"):
            r1 = self.client.get(f"{path}?organization={org1.pk}")
            _assert_vpn_list_filter(response=r1, vpn=vpn1)
            r2 = self.client.get(f"{path}?organization={org2.pk}")
            _assert_vpn_list_filter(response=r2, vpn=vpn2)

        with self.subTest("Test filtering using organization slug"):
            r1 = self.client.get(f"{path}?organization_slug={org1.slug}")
            _assert_vpn_list_filter(response=r1, vpn=vpn1)
            r2 = self.client.get(f"{path}?organization_slug={org2.slug}")
            _assert_vpn_list_filter(response=r2, vpn=vpn2)

    def test_vpn_list_for_shared_objects(self):
        ca = self._create_ca(name="shared_ca", organization=None)
        self._create_cert(ca=ca, name="shared_cert", organization=None)
        org1 = self._get_org()
        test_user = self._create_administrator(organizations=[org1])
        self.client.force_login(test_user)
        path = reverse("config_api:vpn_list")
        r = self.client.get(path, {"format": "api"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "shared_ca</option>")
        self.assertContains(r, "shared_cert</option>")

    # VPN detail having no Org
    def test_vpn_detail_no_org_api(self):
        vpn1 = self._create_vpn(name="test-vpn")
        path = reverse("config_api:vpn_detail", args=[vpn1.pk])
        with self.assertNumQueries(2):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["organization"], None)

    # VPN detail having Org
    def test_vpn_detail_with_org_api(self):
        org = self._get_org()
        vpn1 = self._create_vpn(name="test-vpn", organization=org)
        path = reverse("config_api:vpn_detail", args=[vpn1.pk])
        with self.assertNumQueries(2):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["organization"], org.pk)

    def test_vpn_put_api(self):
        vpn1 = self._create_vpn(name="test-vpn")
        path = reverse("config_api:vpn_detail", args=[vpn1.pk])
        org = self._get_org()
        ca1 = self._create_ca()
        data = {
            "name": "change-test-vpn",
            "host": "vpn1.changetest.com",
            "organization": org.pk,
            "ca": ca1.pk,
            "backend": vpn1.backend,
            "config": vpn1.config,
        }
        r = self.client.put(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "change-test-vpn")
        self.assertEqual(r.data["ca"], ca1.pk)
        self.assertEqual(r.data["organization"], org.pk)

    def test_vpn_patch_api(self):
        vpn1 = self._create_vpn(name="test-vpn")
        path = reverse("config_api:vpn_detail", args=[vpn1.pk])
        data = dict(name="test-vpn-change")
        r = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "test-vpn-change")

    def test_vpn_download_api(self):
        vpn1 = self._create_vpn(name="test-vpn")
        path = reverse("config_api:download_vpn_config", args=[vpn1.pk])
        with self.assertNumQueries(4):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)

    def test_vpn_delete_api(self):
        vpn1 = self._create_vpn(name="test-vpn")
        path = reverse("config_api:vpn_detail", args=[vpn1.pk])
        r = self.client.delete(path)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Vpn.objects.count(), 0)

    def test_get_request_with_change_perm(self):
        change_perm = Permission.objects.filter(codename="change_template")
        user = self._get_user()
        user.user_permissions.add(*change_perm)
        org1 = self._get_org()
        OrganizationUser.objects.create(user=user, organization=org1, is_admin=True)
        self.client.force_login(user)
        t1 = self._create_template(name="t1", organization=self._get_org())
        with self.subTest("Get Template List"):
            path = reverse("config_api:template_list")
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
        with self.subTest("Get Template Detail"):
            path = reverse("config_api:template_detail", args=[t1.pk])
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)

    def test_get_request_with_view_perm(self):
        view_perm = Permission.objects.filter(codename="view_template")
        user = self._get_user()
        user.user_permissions.add(*view_perm)
        org1 = self._get_org()
        OrganizationUser.objects.create(user=user, organization=org1, is_admin=True)
        self.client.force_login(user)
        t1 = self._create_template(name="t1", organization=self._get_org())
        with self.subTest("Get Template List"):
            path = reverse("config_api:template_list")
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
        with self.subTest("Get Template Detail"):
            path = reverse("config_api:template_detail", args=[t1.pk])
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)

    def test_get_request_with_no_perm(self):
        user = self._get_user()
        self.client.force_login(user)
        path = reverse("config_api:template_list")
        response = self.client.get(path)
        self.assertEqual(response.status_code, 403)

    def test_devicegroup_create_api(self):
        self.assertEqual(DeviceGroup.objects.count(), 0)
        org = self._get_org()
        template = self._create_template(name="t1", organization=org)
        path = reverse("config_api:devicegroup_list")
        data = self._devicegroup_data
        data["organization"] = org.pk
        data["templates"] = [str(template.pk)]
        response = self.client.post(path, data, content_type="application/json")
        self.assertEqual(DeviceGroup.objects.count(), 1)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], data["name"])
        self.assertEqual(response.data["description"], data["description"])
        self.assertEqual(response.data["meta_data"], data["meta_data"])
        self.assertEqual(response.data["context"], data["context"])
        self.assertEqual(response.data["organization"], org.pk)
        self.assertEqual(response.data["templates"], [template.pk])

    def test_devicegroup_list_api(self):
        dg = self._create_device_group()
        path = reverse("config_api:devicegroup_list")
        with self.subTest("assert number of queries"):
            with self.assertNumQueries(4):
                r = self.client.get(path)
            self.assertEqual(r.status_code, 200)
        with self.subTest("should not contain default or required templates"):
            t1 = self._create_template(name="t1")
            t2 = self._create_template(name="t2", required=True)
            r = self.client.get(path, {"format": "api"})
            self.assertContains(
                r, f'<option value="{t1.id}">{t1.name}</option>', html=True
            )
            self.assertNotContains(
                r, f'<option value="{t2.id}">{t2.name}</option>', html=True
            )
        with self.subTest("device group list should show most recent first"):
            dg_recent = self._create_device_group(name="Recent")
            dg_old = self._create_device_group(name="Oldest")
            old_date = timezone.now() - timedelta(days=2)
            DeviceGroup.objects.filter(pk=dg_old.pk).update(created=old_date)
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            returned_ids = [group["id"] for group in response.data["results"]]
            expected_order = [str(dg_recent.pk), str(dg.pk), str(dg_old.pk)]
            self.assertEqual(returned_ids, expected_order)

    def test_devicegroup_list_api_filter(self):
        org1 = self._create_org()
        dg1 = self._create_device_group()
        self._create_device(organization=org1)
        org2 = self._create_org(name="test org 2")
        dg2 = self._create_device_group(organization=org2)
        self._create_device(
            mac_address="00:11:22:33:44:66", group=dg2, organization=org2
        )
        path = reverse("config_api:devicegroup_list")

        def _assert_devicegroup_list_filter(response=None, device_group=None):
            self.assertEqual(response.status_code, 200)
            data = response.data
            self.assertEqual(data["count"], 1)
            self.assertEqual(len(data["results"][0]), 9)
            self.assertEqual(data["results"][0]["id"], str(device_group.pk))
            self.assertEqual(data["results"][0]["name"], str(device_group.name))
            self.assertEqual(
                data["results"][0]["organization"], device_group.organization.pk
            )

        with self.subTest("Test filtering using organization id"):
            r1 = self.client.get(f"{path}?organization={org1.pk}")
            _assert_devicegroup_list_filter(response=r1, device_group=dg1)
            r2 = self.client.get(f"{path}?organization={org2.pk}")
            _assert_devicegroup_list_filter(response=r2, device_group=dg2)

        with self.subTest("Test filtering using organization slug"):
            r1 = self.client.get(f"{path}?organization_slug={org1.slug}")
            _assert_devicegroup_list_filter(response=r1, device_group=dg1)
            r2 = self.client.get(f"{path}?organization_slug={org2.slug}")
            _assert_devicegroup_list_filter(response=r2, device_group=dg2)

        with self.subTest("Test filtering using device"):
            r1 = self.client.get(f"{path}?empty=false")
            _assert_devicegroup_list_filter(response=r1, device_group=dg1)
            r2 = self.client.get(f"{path}?empty=true")
            _assert_devicegroup_list_filter(response=r2, device_group=dg2)

    def test_devicegroup_detail_api(self):
        device_group = self._create_device_group()
        path = reverse("config_api:devicegroup_detail", args=[device_group.pk])

        with self.subTest("Test GET"):
            with self.assertNumQueries(3):
                response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["name"], device_group.name)
            self.assertEqual(response.data["description"], device_group.description)
            self.assertDictEqual(response.data["meta_data"], device_group.meta_data)
            self.assertDictEqual(response.data["context"], device_group.context)
            self.assertEqual(
                response.data["organization"], device_group.organization.pk
            )

        with self.subTest("Test PATCH"):
            response = self.client.patch(
                path,
                data={"meta_data": self._devicegroup_data["meta_data"]},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
            device_group.refresh_from_db()
            self.assertDictEqual(
                device_group.meta_data, self._devicegroup_data["meta_data"]
            )

        with self.subTest("Test DELETE"):
            response = self.client.delete(path)
            self.assertEqual(DeviceGroup.objects.count(), 0)

    def test_devicegroup_commonname(self):
        org = self._get_org()
        org2 = self._create_org(name="org2")
        device_group = self._create_device_group(organization=org)
        ca = self._create_ca(organization=org)
        vpn = self._create_vpn(ca=ca, organization=org)
        device = self._create_device(organization=org, group=device_group)
        config = self._create_config(device=device)
        template = self._create_template(type="vpn", vpn=vpn, organization=org)
        config.templates.add(template)
        common_name = (
            config.vpnclient_set.select_related("cert").first().cert.common_name
        )

        with self.subTest("Test with single organization slug"):
            path = reverse("config_api:devicegroup_x509_commonname", args=[common_name])
            response = self.client.get(path, data={"org": org.slug})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["name"], device_group.name)
            self.assertEqual(response.data["description"], device_group.description)
            self.assertDictEqual(response.data["meta_data"], device_group.meta_data)
            self.assertDictEqual(response.data["context"], device_group.context)
            self.assertEqual(
                response.data["organization"], device_group.organization.pk
            )

        with self.subTest("Test with more than one organization slug"):
            path = reverse("config_api:devicegroup_x509_commonname", args=[common_name])
            response = self.client.get(
                path, data={"org": ",".join([org2.slug, org.slug])}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["name"], device_group.name)
            self.assertEqual(response.data["description"], device_group.description)
            self.assertDictEqual(response.data["meta_data"], device_group.meta_data)
            self.assertDictEqual(response.data["context"], device_group.context)
            self.assertEqual(
                response.data["organization"], device_group.organization.pk
            )

    def test_devicegroup_commonname_regressions(self):
        def _assert_response(org_slug, common_name):
            path = reverse(
                "config_api:devicegroup_x509_commonname",
                args=[common_name],
            )
            response = self.client.get(path, data={"org": org_slug})
            self.assertEqual(response.status_code, 404)

        org = self._get_org()
        ca = self._create_ca()
        with self.subTest("Test Cert with organization slug does not exist"):
            _assert_response(
                org_slug="non_existent_org", common_name="random-common-name"
            )

        with self.subTest("Test Cert with common name does not exist"):
            self._create_cert(organization=org, ca=ca)
            _assert_response(org_slug=org.slug, common_name="random-common-name")

        with self.subTest("Test VpnClient with fetched Cert does not exist"):
            self._create_cert(organization=org, common_name="test-cert", ca=ca)
            _assert_response(org_slug=org.slug, common_name="test-cert")

        with self.subTest("Test fetched Device does not have DeviceGroup"):
            vpn = self._create_vpn(ca=ca)
            template = self._create_template(type="vpn", vpn=vpn)
            config = self._create_config(organization=org)
            config.templates.add(template)
            vpnclient = config.vpnclient_set.select_related("cert").first()
            _assert_response(org_slug=org.slug, common_name=vpnclient.cert.common_name)

    @capture_any_output()
    def test_bearer_authentication(self):
        self.client.logout()
        token = self._obtain_auth_token(username="admin", password="tester")
        vpn = self._create_vpn()
        template = self._create_template(type="vpn", vpn=vpn, default=True)
        device_group = self._create_device_group()
        device = self._create_device(group=device_group)
        config = self._create_config(device=device)
        vpnclient_cert = config.vpnclient_set.first().cert

        with self.subTest("Test TemplateListCreateView"):
            response = self.client.get(
                reverse("config_api:template_list"),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test TemplateDetailView"):
            response = self.client.get(
                reverse("config_api:template_detail", args=[template.id]),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test DownloadTemplateconfiguration"):
            response = self.client.get(
                reverse("config_api:download_template_config", args=[template.id]),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test VpnListCreateView"):
            response = self.client.get(
                reverse("config_api:vpn_list"),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test VpnDetailView"):
            response = self.client.get(
                reverse("config_api:vpn_detail", args=[vpn.id]),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test DownloadVpnView"):
            response = self.client.get(
                reverse("config_api:download_vpn_config", args=[vpn.id]),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test DeviceListCreateView"):
            response = self.client.get(
                reverse("config_api:device_list"),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test DeviceDetailView"):
            response = self.client.get(
                reverse("config_api:device_detail", args=[device.id]),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test DeviceGroupListCreateView"):
            response = self.client.get(
                reverse("config_api:devicegroup_list"),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test DeviceGroupDetailView"):
            response = self.client.get(
                reverse("config_api:devicegroup_detail", args=[device_group.id]),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test DeviceGroupCommonName"):
            response = self.client.get(
                reverse(
                    "config_api:devicegroup_x509_commonname",
                    args=[vpnclient_cert.common_name],
                ),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test DownloadDeviceView"):
            response = self.client.get(
                reverse("config_api:download_device_config", args=[device.id]),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)


class TestConfigApiTransaction(
    ApiTestMixin,
    TestAdminMixin,
    CreateConfigTemplateMixin,
    TestVpnX509Mixin,
    CreateDeviceGroupMixin,
    TransactionTestCase,
):
    def setUp(self):
        super().setUp()
        self._login()

    def _get_devicegroup_org_cert(self):
        org = self._get_org()
        device_group = self._create_device_group(organization=org)
        ca = self._create_ca(organization=org)
        vpn = self._create_vpn(ca=ca, organization=org)
        device = self._create_device(organization=org, group=device_group)
        config = self._create_config(device=device)
        template = self._create_template(type="vpn", vpn=vpn, organization=org)
        config.templates.add(template)
        cert = config.vpnclient_set.select_related("cert").first().cert
        return device_group, org, cert

    def test_devicegroup_commonname_caching_on_change(self):
        def _build_cache(path, org_slug):
            response = self.client.get(path, data={"org": org_slug})
            self.assertEqual(response.status_code, 200)

            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)

        def _assert_cache_invalidation(path, org_slug):
            with self.assertNumQueries(5):
                response = self.client.get(path, data={"org": org_slug})
                self.assertEqual(response.status_code, 200)

            with self.assertNumQueries(5):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

        device_group, org, cert = self._get_devicegroup_org_cert()
        path = reverse(
            "config_api:devicegroup_x509_commonname", args=[cert.common_name]
        )

        with self.subTest("Test caching works"):
            _build_cache(path, org.slug)
            with self.assertNumQueries(2):
                response = self.client.get(path, data={"org": org.slug})
                self.assertEqual(response.status_code, 200)

            with self.assertNumQueries(2):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

        with self.subTest("Test cache invalidation when group field of Device changes"):
            device = Device.objects.first()
            device_group2 = self._create_device_group(name="Switches")
            _build_cache(path, org.slug)

            device.group = device_group2
            device.full_clean()
            device.save()

            _assert_cache_invalidation(path, org.slug)

        device.group = device_group
        device.full_clean()
        device.save()

        with self.subTest("Test cache invalidates when DeviceGroup changes"):
            _build_cache(path, org.slug)

            # Invalidate cache
            device_group.organization = self._create_org(name="new-org")
            device_group.save()

            _assert_cache_invalidation(path, org.slug)

        with self.subTest("Test cache invalidates when certificate changes"):
            _build_cache(path, org.slug)

            # Invalidate cache
            cert.renew()

            _assert_cache_invalidation(path, org.slug)

    def test_devicegroup_commonname_cache_invalidates_on_devicegroup_delete(self):
        device_group, org, cert = self._get_devicegroup_org_cert()
        path = reverse(
            "config_api:devicegroup_x509_commonname", args=[cert.common_name]
        )

        with self.assertNumQueries(5):
            response = self.client.get(path, data={"org": org.slug})
            self.assertEqual(response.status_code, 200)

        with self.assertNumQueries(2):
            response = self.client.get(path, data={"org": org.slug})
            self.assertEqual(response.status_code, 200)

        device_group.delete()
        response = self.client.get(path, data={"org": org.slug})
        self.assertEqual(response.status_code, 404)

    def test_devicegroup_commonname_cache_invalidates_on_organization_delete(self):
        device_group, org, cert = self._get_devicegroup_org_cert()
        path = reverse(
            "config_api:devicegroup_x509_commonname", args=[cert.common_name]
        )

        with self.assertNumQueries(5):
            response = self.client.get(path, data={"org": org.slug})
            self.assertEqual(response.status_code, 200)

        with self.assertNumQueries(2):
            response = self.client.get(path, data={"org": org.slug})
            self.assertEqual(response.status_code, 200)

        org.delete()
        response = self.client.get(path, data={"org": org.slug})
        self.assertEqual(response.status_code, 404)

    def test_devicegroup_commonname_cache_invalidates_on_cert_delete(self):
        device_group, org, cert = self._get_devicegroup_org_cert()
        path = reverse(
            "config_api:devicegroup_x509_commonname", args=[cert.common_name]
        )

        with self.assertNumQueries(5):
            response = self.client.get(path, data={"org": org.slug})
            self.assertEqual(response.status_code, 200)

        with self.assertNumQueries(2):
            response = self.client.get(path, data={"org": org.slug})
            self.assertEqual(response.status_code, 200)

        VpnClient.objects.filter(cert=cert).delete()
        response = self.client.get(path, data={"org": org.slug})
        self.assertEqual(response.status_code, 404)

    def test_devicegroup_templates_change(self):
        org = self._get_org()
        t1 = self._create_template(name="t1", organization=org)
        t2 = self._create_template(name="t2", organization=org)
        dg = self._create_device_group(name="test-group", organization=org)
        dg.templates.add(t1)
        path = reverse("config_api:devicegroup_detail", args=[dg.pk])
        data = {
            "templates": [str(t2.pk)],
        }
        with catch_signal(group_templates_changed) as mocked_group_templates_changed:
            response = self.client.patch(path, data, content_type="application/json")
            self.assertEqual(response.json().get("templates"), [str(t2.pk)])
        mocked_group_templates_changed.assert_called_once_with(
            signal=group_templates_changed,
            sender=DeviceGroup,
            instance=dg,
            templates=[t2.pk],
            old_templates=[t1.pk],
        )

    def test_device_api_change_group(self):
        t1 = self._create_template(name="t1")
        t2 = self._create_template(name="t2")
        dg1 = self._create_device_group(name="dg-1")
        dg2 = self._create_device_group(name="dg-2")
        dg1.templates.add(t1)
        dg2.templates.add(t2)
        d1 = self._create_device(name="test-device", group=dg1)
        path = reverse("config_api:device_detail", args=[d1.pk])
        data = {
            "name": "change-test-device",
            "organization": d1.organization.pk,
            "mac_address": d1.mac_address,
            "group": dg2.pk,
            "config": {
                "backend": d1.config.backend,
                "status": "modified",
                "templates": [],
                "context": {},
                "config": {},
            },
        }
        with self.subTest("detail device api should show group templates"):
            r = self.client.get(path, content_type="application/json")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data["group"], dg1.pk)
            self.assertEqual(r.data["config"]["templates"], [t1.pk])
            self.assertIn(t1, d1.config.templates.all())

        with self.subTest("change group should change device templates"):
            r = self.client.put(path, data, content_type="application/json")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data["group"], dg2.pk)
            self.assertEqual(r.data["config"]["templates"], [t2.pk])
            self.assertIn(t2, d1.config.templates.all())

        with self.subTest("unassign group should remove group templates"):
            data["group"] = ""
            r = self.client.put(path, data, content_type="application/json")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data["group"], None)
            self.assertEqual(r.data["config"]["templates"], [])
            self.assertEqual(d1.config.templates.count(), 0)

    def test_device_detail_api_change_config(self):
        org = self._get_org()
        vpn = self._create_vpn(organization=org)
        vpn_template = self._create_template(
            type="vpn", vpn=vpn, organization=org, name="VPN Client"
        )
        template = self._create_template()
        data = {
            "name": "change-test-device",
            "organization": str(org.id),
            "mac_address": "00:11:22:33:44:55",
            "config": {},
        }

        with self.subTest("Test creating new device without config"):
            response = self.client.post(reverse("config_api:device_list"), data)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(Device.objects.count(), 1)

        device = Device.objects.first()
        path = reverse("config_api:device_detail", args=[device.pk])

        with self.subTest("Test creating config for device"):
            data["config"] = {
                "backend": "netjsonconfig.OpenWrt",
                "templates": [],
                "context": {"lan_ip": "192.168.1.1"},
                "config": {"interfaces": [{"name": "wlan0", "type": "wireless"}]},
            }
            response = self.client.put(path, data, content_type="application/json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(Config.objects.count(), 1)
            config = Config.objects.first()
            self.assertEqual(config.config, data["config"]["config"])
            self.assertEqual(config.context, data["config"]["context"])

        with self.subTest("Test adding templates"):
            data["config"]["templates"] = [str(template.pk), str(vpn_template.pk)]
            response = self.client.put(path, data, content_type="application/json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(device.config.templates.count(), 2)
            self.assertEqual(device.config.vpnclient_set.count(), 1)

        with self.subTest("Test removing VPN template"):
            data["config"]["templates"] = [str(template.pk)]
            response = self.client.put(path, data, content_type="application/json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(device.config.templates.count(), 1)
            self.assertEqual(device.config.vpnclient_set.count(), 0)

        with self.subTest("Remove all templates"):
            data["config"]["templates"] = []
            response = self.client.put(path, data, content_type="application/json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(device.config.templates.count(), 0)

    def test_multiple_vpn_client_templates_same_vpn(self):
        """
        Assigning multiple templates of type 'vpn' referencing the same VPN
        to a device's config raises error.
        """
        org = self._get_org()
        vpn = self._create_vpn(organization=org)
        # Create two templates of type 'vpn' referencing the same VPN
        vpn_template1 = self._create_template(
            type="vpn", vpn=vpn, organization=org, name="VPN Client 1"
        )
        vpn_template2 = self._create_template(
            type="vpn", vpn=vpn, organization=org, name="VPN Client 2"
        )
        device = self._create_device(organization=org)
        config = self._create_config(device=device)
        path = reverse("config_api:device_detail", args=[device.pk])
        data = {
            "name": device.name,
            "organization": str(org.id),
            "mac_address": device.mac_address,
            "config": {
                "backend": "netjsonconfig.OpenWrt",
                "context": {"lan_ip": "192.168.1.1"},
                "config": {"interfaces": [{"name": "wlan0", "type": "wireless"}]},
            },
        }
        expected_error_message = (
            "You cannot select multiple VPN client templates related"
            " to the same VPN server.\n"
            'The templates "VPN Client 1" and "VPN Client 2" are all '
            'linked to the same VPN server: "test".'
        )

        with self.subTest("Add both templates at once"):
            data["config"]["templates"] = [str(vpn_template1.pk), str(vpn_template2.pk)]
            response = self.client.put(path, data, content_type="application/json")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                str(response.data["config"][0]),
                expected_error_message,
            )
            self.assertEqual(config.templates.count(), 0)
            self.assertEqual(config.vpnclient_set.count(), 0)

        with self.subTest("Add one template at a time"):
            data["config"]["templates"] = [str(vpn_template1.pk)]
            response = self.client.put(path, data, content_type="application/json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(config.templates.count(), 1)
            self.assertEqual(config.vpnclient_set.count(), 1)

            # Now add the second template
            data["config"]["templates"] = [str(vpn_template1.pk), str(vpn_template2.pk)]
            response = self.client.put(path, data, content_type="application/json")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                str(response.data["config"][0]),
                expected_error_message,
            )
            self.assertEqual(config.templates.filter(id=vpn_template1.id).count(), 1)
            self.assertEqual(config.vpnclient_set.count(), 1)

        with self.subTest("Change existing template with another"):
            data["config"]["templates"] = [str(vpn_template2.pk)]
            response = self.client.put(path, data, content_type="application/json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(config.templates.filter(id=vpn_template2.id).count(), 1)
            self.assertEqual(config.vpnclient_set.count(), 1)

    def test_device_patch_with_templates_of_same_org(self):
        org1 = self._create_org(name="testorg")
        d1 = self._create_device(name="org1-config", organization=org1)
        self._create_config(device=d1)
        self.assertEqual(d1.config.templates.count(), 0)
        path = reverse("config_api:device_detail", args=[d1.pk])
        t1 = self._create_template(name="t1", organization=None)
        t2 = self._create_template(name="t2", organization=org1)
        data = {"config": {"templates": [str(t1.id), str(t2.id)]}}
        r = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(d1.config.templates.count(), 2)
        self.assertEqual(r.data["config"]["templates"], [t1.id, t2.id])

    @patch.object(Config, "_CONFIG_MODIFIED_TIMEOUT", 3)
    def test_config_modified_signal(self):
        """
        Verifies that config_modified signal is sent only once.
        """
        template1 = self._create_template(
            default_values={"ssid": "OpenWISP"},
        )
        template2 = self._create_template(
            name="template2",
            config={"interfaces": [{"name": "{{ ifname }}", "type": "ethernet"}]},
            default_values={"ifname": "eth1"},
        )
        data = self._device_data
        org = self._get_org()
        data["organization"] = org.pk
        data["config"]["templates"] = [str(template1.pk), str(template2.pk)]
        response = self.client.post(
            reverse("config_api:device_list"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Device.objects.count(), 1)
        config = Device.objects.first().config
        self.assertEqual(config.templates.count(), 2)
        device_detail = reverse("config_api:device_detail", args=[config.device_id])

        with self.subTest(
            "Updating the unused context variable does not send config_modified signal"
        ):
            with patch(
                "openwisp_controller.config.signals.config_modified.send"
            ) as mocked_signal:
                data["config"]["context"]["ssid"] = "Updated"
                response = self.client.patch(
                    device_detail,
                    {"config": data["config"]},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 200)
                config.refresh_from_db()
                self.assertEqual(config.context["ssid"], "Updated")
                mocked_signal.assert_not_called()

        config._delete_config_modified_timeout_cache()
        with self.subTest(
            "Changing used context variable sends config_modified signal"
        ):
            with patch(
                "openwisp_controller.config.signals.config_modified.send"
            ) as mocked_signal:
                data["config"]["context"] = {"ssid": "Updated", "ifname": "eth2"}
                response = self.client.patch(
                    device_detail,
                    {"config": data["config"]},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 200)
                config.refresh_from_db()
                self.assertEqual(
                    config.context["ssid"],
                    "Updated",
                )
                self.assertEqual(config.status, "modified")
                mocked_signal.assert_called_once()

        config._delete_config_modified_timeout_cache()
        with self.subTest("Changing device configuration sends config_modified signal"):
            with patch(
                "openwisp_controller.config.signals.config_modified.send"
            ) as mocked_signal:
                data["config"]["config"]["interfaces"] = [
                    {"name": "eth5", "type": "ethernet"}
                ]
                response = self.client.patch(
                    device_detail, data, content_type="application/json"
                )
                self.assertEqual(response.status_code, 200)
                config.refresh_from_db()
                self.assertEqual(
                    config.config["interfaces"][0]["name"],
                    "eth5",
                )
                self.assertEqual(config.status, "modified")
                mocked_signal.assert_called_once()

        config._delete_config_modified_timeout_cache()
        with self.subTest("Changing applied template sends config_modified signal"):
            with patch(
                "openwisp_controller.config.signals.config_modified.send"
            ) as mocked_signal:
                data = {"default_values": {"ifname": "eth3"}}
                response = self.client.patch(
                    reverse("config_api:template_detail", args=[template2.pk]),
                    data,
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 200)
                template2.refresh_from_db()
                self.assertEqual(template2.default_values["ifname"], "eth3")
                mocked_signal.assert_called_once()
