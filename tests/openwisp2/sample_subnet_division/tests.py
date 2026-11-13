from django.test import TestCase
from django.urls import reverse

from openwisp_controller.config.tests.utils import TestWireguardVpnMixin
from openwisp_controller.subnet_division.tests.helpers import SubnetDivisionTestMixin
from openwisp_controller.subnet_division.tests.test_admin import (
    TestDeviceAdmin as BaseTestDeviceAdmin,
)
from openwisp_controller.subnet_division.tests.test_admin import (
    TestIPAdmin as BaseTestIPAdmin,
)
from openwisp_controller.subnet_division.tests.test_admin import (
    TestSubnetAdmin as BaseTestSubnetAdmin,
)
from openwisp_controller.subnet_division.tests.test_models import (
    TestSubnetDivisionRule as BaseTestSubnetDivisionRule,
)
from openwisp_controller.tests.utils import TestAdminMixin


class TestDeviceAdmin(BaseTestDeviceAdmin):
    config_label = "sample_config"


class TestSubnetAdmin(BaseTestSubnetAdmin):
    config_label = "sample_config"


class TestSubnetDivsionRule(BaseTestSubnetDivisionRule):
    config_label = "sample_config"


class TestIPAdmin(BaseTestIPAdmin):
    pass


class TestSampleSubnetDeletionApi(
    TestAdminMixin,
    SubnetDivisionTestMixin,
    TestWireguardVpnMixin,
    TestCase,
):
    def setUp(self):
        super().setUp()
        self.org = self._get_org()
        self.master_subnet = self._get_master_subnet()
        self.config = self._create_config(organization=self.org)
        self.rule = self._get_vpn_subdivision_rule(number_of_ips=1, number_of_subnets=1)
        self._mock_subnet_division_rule(self.config, self.master_subnet, self.rule)
        self._login()

    def test_delete_in_use_subnet_returns_validation_error(self):
        url = reverse("ipam:subnet", args=[self.master_subnet.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 400)
        self.assertIn("used by device configurations", str(response.data))
        self.assertTrue(self.rule.__class__.objects.filter(pk=self.rule.pk).exists())


del BaseTestDeviceAdmin
del BaseTestSubnetAdmin
del BaseTestSubnetDivisionRule
del BaseTestIPAdmin
