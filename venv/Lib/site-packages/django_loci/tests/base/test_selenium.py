from time import sleep

from django.urls.base import reverse
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from openwisp_utils.tests import SeleniumTestMixin

from .. import TestAdminInlineMixin, TestLociMixin


class BaseTestDeviceAdminSelenium(
    SeleniumTestMixin, TestAdminInlineMixin, TestLociMixin
):
    app_label = "django_loci"

    def _fill_device_form(self):
        """
        This method can be extended by downstream implementations
        needing more complex logic to fill the device form
        """
        self.find_element(by=By.NAME, value="name").send_keys("11:22:33:44:55:66")

    def test_create_new_device(self):
        self.login()
        self.open(reverse(self.add_url))
        self._fill_device_form()
        select = Select(
            self.find_element(
                by=By.NAME, value=f"{self._get_prefix()}-0-location_selection"
            )
        )
        select.select_by_value("new")

        select = Select(
            self.find_element(by=By.NAME, value=f"{self._get_prefix()}-0-type")
        )
        select.select_by_value("outdoor")

        self.find_element(by=By.NAME, value=f"{self._get_prefix()}-0-name").send_keys(
            "Test Location"
        )
        # use the marker button to select location on map
        self.find_element(
            by=By.XPATH, value='//a[@class="leaflet-draw-draw-marker"]'
        ).click()
        action = ActionChains(self.web_driver)
        # place the marker on the map at a random location
        elem = self.find_element(
            by=By.ID, value=f"id_{self._get_prefix()}-0-geometry-map"
        )
        # (15, 5) is a random offset from the top left corner of the map
        action.move_to_element(elem).move_by_offset(15, 5).click().perform()
        # Wait until address field gets populated with the location marked above
        WebDriverWait(self.web_driver, 5).until(
            lambda x: x.find_element(
                by=By.XPATH, value=f'//input[@name="{self._get_prefix()}-0-address"]'
            )
            .get_attribute("value")
            .strip()
            not in ("", None)
        )

        self.find_element(by=By.NAME, value="_save").click()
        self.wait_for_presence(By.CSS_SELECTOR, ".messagelist .success")
        # device model verbose name is dynamic
        object_verbose_name = self.object_model._meta.verbose_name
        self.assertEqual(
            self.find_elements(by=By.CLASS_NAME, value="success")[0].text,
            f"The {object_verbose_name} “11:22:33:44:55:66” was added successfully.",
        )

    def test_real_time_update_address_field(self):
        location = self._create_location()
        self.login()
        url = reverse(f"admin:{self.app_label}_location_change", args=[location.id])
        self.open(url)
        # Changing the address in tab 1 should update it in tab 0 in real time without a page reload
        self.web_driver.switch_to.new_window("tab")
        tabs = self.web_driver.window_handles
        # Swtich to last tab
        self.web_driver.switch_to.window(tabs[-1])
        self.open(url)
        address_input = self.find_element(by=By.ID, value="id_address")
        self.assertEqual(address_input.get_attribute("value"), location.address)
        self.find_element(
            by=By.XPATH, value='//a[@class="leaflet-draw-draw-marker"]'
        ).click()
        elem = self.find_element(by=By.ID, value="id_geometry-map")
        # Updating the marker to a random new location
        ActionChains(self.web_driver).move_to_element(elem).move_by_offset(
            30, 15
        ).click().perform()
        alert = WebDriverWait(self.web_driver, 2).until(EC.alert_is_present())
        alert.accept()
        sleep(0.05)
        new_address = "Lazio 00185, ITA"
        address_input = self.find_element(by=By.ID, value="id_address")
        self.assertIn(new_address, address_input.get_attribute("value"))
        self.wait_for("element_to_be_clickable", by=By.NAME, value="_continue").click()
        # Close tab[1] so other tests are not affected
        self.web_driver.close()
        # on some systems the zero tab may be an empty tab
        # hence we open the tab before the last one
        initial_tab = tabs.index(tabs[-1]) - 1
        self.web_driver.switch_to.window(tabs[initial_tab])
        address_input = self.find_element(by=By.ID, value="id_address")
        self.assertIn(new_address, address_input.get_attribute("value"))
