from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls import reverse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from swapper import load_model

from openwisp_utils.tests import SeleniumTestMixin

from .helpers import SubnetDivisionTestMixin

SubnetDivisionRule = load_model("subnet_division", "SubnetDivisionRule")


@tag("selenium_tests")
class TestSubnetAdmin(
    SeleniumTestMixin, SubnetDivisionTestMixin, StaticLiveServerTestCase
):
    def test_rule_organization_of_non_shared_subnet(self):
        org = self._get_org()
        prefix = "subnetdivisionrule_set-0"
        self.login()
        self.open(reverse("admin:openwisp_ipam_subnet_add"))
        self.find_element(By.CSS_SELECTOR, "#select2-id_organization-container").click()
        self.wait_for_invisibility(
            By.CSS_SELECTOR, ".select2-results__option.loading-results"
        )
        self.find_element(By.CLASS_NAME, "select2-search__field").send_keys(org.name)
        self.wait_for_invisibility(
            By.CSS_SELECTOR, ".select2-results__option.loading-results"
        )
        self.find_element(By.CLASS_NAME, "select2-results__option").click()
        self.find_element(
            By.CSS_SELECTOR, "#subnetdivisionrule_set-group .add-row a"
        ).click()
        self.wait_for_invisibility(
            By.CSS_SELECTOR, f"#{prefix} .form-row.field-organization"
        )
        self.assertEqual(
            self.find_element(
                By.NAME, f"{prefix}-organization", wait_for="presence"
            ).get_attribute("value"),
            str(org.pk),
        )
        self.find_element(By.NAME, "name").send_keys("Test")
        self.find_element(By.NAME, "subnet").send_keys("10.0.0.0/16")
        Select(self.find_element(By.NAME, f"{prefix}-type")).select_by_index(1)
        self.find_element(By.NAME, f"{prefix}-label").send_keys("TEST")
        for field, value in (
            ("number_of_subnets", "2"),
            ("size", "24"),
            ("number_of_ips", "2"),
        ):
            element = self.find_element(By.NAME, f"{prefix}-{field}")
            element.clear()
            element.send_keys(value)
        self.find_element(By.NAME, "_save").click()
        self.wait_for_admin_success_message()
        self.assertEqual(SubnetDivisionRule.objects.get(label="TEST").organization, org)
        self.assert_no_browser_errors()
