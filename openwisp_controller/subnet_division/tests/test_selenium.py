from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls import reverse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from swapper import load_model

from ...config.tests.test_selenium import SeleniumTestMixin
from .helpers import SubnetDivisionTestMixin

SubnetDivisionRule = load_model("subnet_division", "SubnetDivisionRule")


@tag("selenium_tests")
class TestSubnetAdminSelenium(
    SeleniumTestMixin,
    SubnetDivisionTestMixin,
    StaticLiveServerTestCase,
):
    ipam_label = "openwisp_ipam"

    def _add_rule(self):
        self.find_element(
            By.CSS_SELECTOR, "#subnetdivisionrule_set-group .add-row a"
        ).click()
        self.wait_for_presence(By.NAME, "subnetdivisionrule_set-0-organization")

    def _save(self):
        # Hide user tools because it covers the save button
        self.web_driver.execute_script(
            'document.querySelector("#ow-user-tools").style.display="none"'
        )
        self.find_element(By.NAME, "_save").click()
        self.wait_for_admin_success_message()

    def test_rule_organization_field(self):
        org = self._get_org()
        self.login()

        with self.subTest("Hidden and set if subnet has an organization"):
            self.open(reverse(f"admin:{self.ipam_label}_subnet_add"))
            self.find_element(By.NAME, "name").send_keys("Subnet")
            self.find_element(By.NAME, "subnet").send_keys("10.0.0.0/16")
            self._select_organization(org)
            self._add_rule()
            self.wait_for_invisibility(
                By.CSS_SELECTOR, "#subnetdivisionrule_set-0 .field-organization"
            )
            Select(
                self.find_element(By.NAME, "subnetdivisionrule_set-0-type")
            ).select_by_index(1)
            self.find_element(By.NAME, "subnetdivisionrule_set-0-label").send_keys(
                "LAN"
            )
            for field, value in (
                ("size", "24"),
                ("number_of_subnets", "1"),
                ("number_of_ips", "2"),
            ):
                element = self.find_element(
                    By.NAME, f"subnetdivisionrule_set-0-{field}"
                )
                element.clear()
                element.send_keys(value)
            self._save()
            self.assertEqual(
                SubnetDivisionRule.objects.get(label="LAN").organization, org
            )

        with self.subTest("Shown if subnet is shared"):
            subnet = self._create_subnet(subnet="10.1.0.0/16", organization=None)
            self.open(
                reverse(f"admin:{self.ipam_label}_subnet_change", args=[subnet.pk])
            )
            self._add_rule()
            self.wait_for_visibility(
                By.CSS_SELECTOR, "#subnetdivisionrule_set-0 .field-organization"
            )

        with self.subTest("Shown if saved rule has a different organization"):
            org2 = self._create_org(name="org2")
            subnet = self._create_subnet(subnet="10.2.0.0/16", organization=None)
            self._get_vpn_subdivision_rule(
                master_subnet=subnet, organization=org2, label="VPN"
            )
            self.open(
                reverse(f"admin:{self.ipam_label}_subnet_change", args=[subnet.pk])
            )
            self._select_organization(org)
            self.wait_for_visibility(
                By.CSS_SELECTOR, "#subnetdivisionrule_set-0 .field-organization"
            )
            self.assertEqual(
                self.find_element(
                    By.NAME,
                    "subnetdivisionrule_set-0-organization",
                    wait_for="presence",
                ).get_attribute("value"),
                str(org2.pk),
            )

    def test_empty_rule_ignored(self):
        org = self._get_org()
        subnet = self._create_subnet(subnet="10.0.0.0/16", organization=org)
        self.login()
        self.open(reverse(f"admin:{self.ipam_label}_subnet_change", args=[subnet.pk]))
        self._add_rule()
        self._save()
        self.assertEqual(SubnetDivisionRule.objects.count(), 0)
