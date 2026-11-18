from importlib import import_module
from unittest.mock import patch

from django.apps.registry import Apps
from django.contrib.auth.models import Permission
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from openwisp_controller.config.tests.utils import TestWireguardVpnMixin
from openwisp_controller.tests.utils import TestAdminMixin

from ..apps import SubnetDivisionConfig
from .helpers import SubnetDivisionTestMixin


class TestDeviceSubnetDivisionRuleApiFilter(
    TestAdminMixin,
    SubnetDivisionTestMixin,
    TestWireguardVpnMixin,
    TestCase,
):
    def setUp(self):
        super().setUp()
        self._setup_subnet_division_api_fixture()

    def test_device_list_filter_by_subnet_division_rule(self):
        config2 = self._create_config(
            device=self._create_device(name="device-2", mac_address="00:11:22:33:44:56")
        )
        rule2 = self._get_vpn_subdivision_rule(
            number_of_ips=1, number_of_subnets=1, label="VPN2"
        )
        self._mock_subnet_division_rule(config2, self.master_subnet, rule2)
        path = reverse("config_api:device_list")
        response = self.client.get(path, {"subnet_division_rule": self.rule.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.config.device.pk))

        with self.subTest("Malformed UUID returns a validation error"):
            response = self.client.get(path, {"subnet_division_rule": "invalid-uuid"})
            self.assertEqual(response.status_code, 400)

        with self.subTest("Valid UUID without a matching rule returns no device"):
            response = self.client.get(
                path,
                {"subnet_division_rule": "8bbc4b0e-0a3a-4f5e-9d9f-1a2b3c4d5e6f"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 0)

    def test_device_list_filter_by_template_and_subnet_division_rule(self):
        """The two filters must be combined, not applied exclusively."""
        template = self._create_template(organization=self.org)
        self.config.templates.add(template)

        config2 = self._create_config(
            device=self._create_device(
                name="device-no-template", mac_address="00:11:22:33:44:77"
            )
        )
        self._mock_subnet_division_rule(config2, self.master_subnet, self.rule)
        config3 = self._create_config(
            device=self._create_device(
                name="device-other-rule", mac_address="00:11:22:33:44:78"
            )
        )
        config3.templates.add(template)
        rule2 = self._get_vpn_subdivision_rule(
            number_of_ips=1, number_of_subnets=1, label="VPN2"
        )
        self._mock_subnet_division_rule(config3, self.master_subnet, rule2)

        path = reverse("config_api:device_list")
        response = self.client.get(
            path,
            {
                "config__templates": str(template.pk),
                "subnet_division_rule": str(self.rule.id),
            },
        )

        self.assertEqual(response.status_code, 200)
        # only the device which matches *both* filters is returned
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.config.device.pk))

    def test_device_list_filter_by_other_organization_rule(self):
        """An operator cannot see devices of another organization.

        Filtering by a rule which belongs to an organization the user does
        not manage must not disclose the related devices. The shipped Operator
        group lacks ``view_device``, so that permission is granted directly to
        let this test reach the organization-scope check.
        """
        other_org = self._create_org(name="other-org", slug="other-org")
        other_master_subnet = self._get_master_subnet(
            subnet="172.20.0.0/16", organization=other_org
        )
        other_config = self._create_config(
            device=self._create_device(
                name="other-org-device",
                mac_address="00:11:22:33:44:88",
                organization=other_org,
            )
        )
        other_rule = self._get_vpn_subdivision_rule(
            number_of_ips=1,
            number_of_subnets=1,
            label="OtherOrgVPN",
            organization=other_org,
            master_subnet=other_master_subnet,
        )
        self._mock_subnet_division_rule(other_config, other_master_subnet, other_rule)
        operator = self._create_operator(organizations=[other_org])
        operator.user_permissions.add(
            *Permission.objects.filter(codename="view_device")
        )
        self.client.force_login(operator)

        path = reverse("config_api:device_list")
        response = self.client.get(path, {"subnet_division_rule": self.rule.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

        response = self.client.get(path, {"subnet_division_rule": other_rule.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(other_config.device_id))


class TestIPAMURLSelection(SimpleTestCase):
    def test_explicit_subnet_division_app_config(self):
        from openwisp_controller.urls import get_ipam_urls_module

        app_name = "openwisp_controller.subnet_division"
        registry = Apps(installed_apps=[])
        app_config = SubnetDivisionConfig(app_name, import_module(app_name))
        app_config.apps = registry
        registry.app_configs[app_config.label] = app_config

        with (
            patch("openwisp_controller.urls.apps", registry),
            self.settings(EXTENDED_APPS=()),
        ):
            self.assertEqual(
                get_ipam_urls_module(),
                "openwisp_controller.subnet_division.ipam_urls",
            )
