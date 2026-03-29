from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls import reverse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from openwisp_notifications.signals import notify
from openwisp_notifications.swapper import load_model, swapper_load_model
from openwisp_notifications.utils import _get_object_link, get_unsubscribe_url_for_user
from openwisp_users.tests.utils import TestOrganizationMixin
from openwisp_utils.tests import SeleniumTestMixin

from .test_helpers import mock_notification_types, register_notification_type

Notification = load_model("Notification")
NotificationSetting = load_model("NotificationSetting")
Organization = swapper_load_model("openwisp_users", "Organization")
OrganizationUser = swapper_load_model("openwisp_users", "OrganizationUser")


@tag("selenium_tests")
class TestSelenium(
    SeleniumTestMixin,
    TestOrganizationMixin,
    StaticLiveServerTestCase,
):
    users_app_label = "openwisp_users"

    def setUp(self):
        super().setUp()
        org = self._create_org()
        OrganizationUser.objects.create(user=self.admin, organization=org)
        self.operator = super()._get_operator()
        self.notification_options = dict(
            sender=self.admin,
            recipient=self.admin,
            verb="Test Notification",
            email_subject="Test Email subject",
            action_object=self.operator,
            target=self.operator,
            type="default",
        )

    def _create_notification(self):
        return notify.send(**self.notification_options)

    @mock_notification_types
    def test_notification_relative_link(self):
        test_type = {
            "verbose_name": "Test Notification Type",
            "level": "warning",
            "verb": "testing",
            "message": "Test notification for {notification.target.pk}",
            "email_subject": "[{site.name}] {notification.target.pk}",
            "target_link": (
                "openwisp_notifications.tests.test_helpers.notification_related_object_url"
            ),
        }
        register_notification_type("test_type", test_type)
        self.login()

        with self.subTest("Verify URL for default notification type"):
            default_notification = self._create_notification().pop()[1][0]
            self.find_element(By.ID, "openwisp_notifications").click()
            self.wait_for_visibility(By.CLASS_NAME, "ow-notification-elem")
            notification_elem = self.find_element(By.CLASS_NAME, "ow-notification-elem")
            data_location_value = notification_elem.get_attribute("data-location")
            self.assertEqual(
                data_location_value,
                _get_object_link(default_notification.target, False),
            )

        self.open(reverse("admin:index"))
        with self.subTest("Verify URL for test notification type"):
            self.notification_options.update({"type": "test_type"})
            self._create_notification().pop()[1][0]
            self.find_element(By.ID, "openwisp_notifications").click()
            self.wait_for_visibility(By.CLASS_NAME, "ow-notification-elem")
            notification_elem = self.find_element(By.CLASS_NAME, "ow-notification-elem")
            data_location_value = notification_elem.get_attribute("data-location")
            self.assertEqual(data_location_value, "/index#heading")

    def test_notification_dialog(self):
        self.login()
        self.notification_options.update(
            {"message": "Test Message", "description": "Test Description"}
        )
        notification = self._create_notification().pop()[1][0]

        with self.subTest(
            "Notification dialog opens automatically on #notification fragment"
        ):
            self.open("{}#notifications".format(reverse("admin:index")))
            # Since the above open() operation only changes the fragment,
            # we need to refresh to page to simulate loading of page with fragment
            self.web_driver.refresh()
            self._wait_until_page_ready()
            self.wait_for_visibility(By.CLASS_NAME, "ow-notification-dropdown")
            self.wait_for_visibility(By.CLASS_NAME, "ow-notification-elem")

            # Dialog is not closed on programmatic click events
            self.web_driver.execute_script('django.jQuery("#main").trigger("click");')
            self.wait_for_visibility(By.CLASS_NAME, "ow-notification-dropdown")
            self.wait_for_visibility(By.CLASS_NAME, "ow-notification-elem")

            # Dialog is closed on user click events
            self.web_driver.find_element(By.ID, "main").click()
            self.wait_for_invisibility(By.CLASS_NAME, "ow-notification-dropdown")
            self.wait_for_invisibility(By.CLASS_NAME, "ow-notification-elem")

        with self.subTest("Open notification dialog by clicking notification button"):
            self.find_element(By.ID, "openwisp_notifications").click()
            self.wait_for_visibility(By.ID, f"ow-{notification.id}")
            self.find_element(By.ID, f"ow-{notification.id}").click()
            self.wait_for_visibility(By.CLASS_NAME, "ow-dialog-notification")
            dialog = self.find_element(By.CLASS_NAME, "ow-dialog-notification")
            self.assertEqual(
                dialog.find_element(By.CLASS_NAME, "ow-message-title").text,
                "Test Message",
            )
            self.assertEqual(
                dialog.find_element(By.CLASS_NAME, "ow-message-description").text,
                "Test Description",
            )

    def test_notification_dialog_open_button_visibility(self):
        self.login()
        self.notification_options.pop("target")
        self.notification_options.update(
            {"message": "Test Message", "description": "Test Description"}
        )
        notification = self._create_notification().pop()[1][0]
        self.find_element(By.ID, "openwisp_notifications").click()
        self.find_element(By.ID, f"ow-{notification.id}").click()
        dialog = self.find_element(By.CLASS_NAME, "ow-dialog-notification")
        # This confirms the button is hidden
        dialog.find_element(By.CSS_SELECTOR, ".ow-message-target-redirect.ow-hide")

    def test_email_unsubscribe_page(self):
        with self.subTest("Token is invalid"):
            self.open(reverse("notifications:unsubscribe"))
            self.assertEqual(
                self.find_element(By.TAG_NAME, "h2").text, "Invalid or Expired Link"
            )
            self.assertEqual(len(self.get_browser_logs()), 0)

        with self.subTest("User unsubscribe with valid URL"):
            unsubscribe_link = get_unsubscribe_url_for_user(self.admin, False)
            self.open(unsubscribe_link)
            self.wait_for_visibility(By.ID, "subscribed-message")
            self.wait_for_invisibility(By.ID, "unsubscribed-message")
            toggle_btn = self.find_element(By.ID, "toggle-btn")
            self.assertEqual(toggle_btn.text, "Unsubscribe")
            toggle_btn.click()
            self.wait_for_visibility(By.ID, "confirm-unsubscribed")
            self.wait_for_invisibility(By.ID, "confirm-subscribed")
            self.assertEqual(self.find_element(By.ID, "toggle-btn").text, "Subscribe")
            self.assertEqual(len(self.get_browser_logs()), 0)

        with self.subTest("User subscribe to notifications again"):
            self.open(unsubscribe_link)
            self.wait_for_visibility(By.ID, "unsubscribed-message")
            self.wait_for_invisibility(By.ID, "subscribed-message")
            toggle_btn = self.find_element(By.ID, "toggle-btn")
            self.assertEqual(toggle_btn.text, "Subscribe")
            toggle_btn.click()
            self.wait_for_visibility(By.ID, "confirm-subscribed")
            self.wait_for_invisibility(By.ID, "confirm-unsubscribed")
            self.assertEqual(self.find_element(By.ID, "toggle-btn").text, "Unsubscribe")
            self.assertEqual(len(self.get_browser_logs()), 0)

        with self.subTest("Network request fails"):
            self.open(unsubscribe_link)
            self.web_driver.execute_script(
                """
                window.fetch = function() {
                    return Promise.reject(new Error('Simulated fetch failure'));
                };
            """
            )
            self.web_driver.find_element(By.ID, "toggle-btn").click()
            self.wait_for_visibility(By.ID, "error-msg")
            browser_logs = self.get_browser_logs()
            self.assertEqual(len(browser_logs), 1)
            self.assertIn("Error updating subscription", browser_logs[0]["message"])

    def test_notification_preference_page(self):
        self.login()
        self.open(reverse("notifications:notification_preference"))
        # Expand the first organization panel
        self.find_element(By.CSS_SELECTOR, ".toggle-icon").click()

        with self.subTest("Generic message type is not present"):
            # Verify that the generic message type is not present
            self.wait_for_invisibility(By.XPATH, '//td[text()="Generic Message Type"]')

        with self.subTest("Notifications are enabled"):
            # All web notifications are enabled
            web_checkboxes = self.find_elements(
                By.CSS_SELECTOR,
                'input[type="checkbox"][data-column="web"]',
                wait_for="presence",
            )
            for checkbox in web_checkboxes:
                self.assertEqual(checkbox.is_selected(), True)
            # Email notification is enabled for default type
            default_email_checkbox = self.find_element(
                By.CSS_SELECTOR,
                "label#org-1-email-1 input",
                wait_for="presence",
            )
            self.assertTrue(default_email_checkbox.is_selected())

        with self.subTest("Disabling global notification setting"):
            self.find_element(
                By.CSS_SELECTOR,
                ".global-setting-dropdown[data-web-state] .global-setting-dropdown-toggle",
            ).click()
            self.find_element(
                By.CSS_SELECTOR,
                ".global-setting-dropdown[data-web-state]"
                " .global-setting-dropdown-menu button:last-child",
            ).click()
            self.find_element(By.CSS_SELECTOR, "#confirmation-modal #confirm").click()

            all_checkboxes = self.find_elements(
                By.CSS_SELECTOR, 'input[type="checkbox"]', wait_for="presence"
            )
            for checkbox in all_checkboxes:
                self.assertFalse(checkbox.is_selected())
                # Verify database has NotificationSetting.web set to False
                if pk := checkbox.get_attribute("data-pk"):
                    self.assertEqual(NotificationSetting.objects.get(pk=pk).web, False)

        with self.subTest("Enabling organization-level web notification"):
            # Check the org-level web checkbox
            org_level_web_checkbox = self.find_element(By.CSS_SELECTOR, "#org-1-web")
            org_level_web_checkbox.click()

            # Verify that all web checkboxes under org-1 are selected
            web_checkboxes = self.find_elements(
                By.CSS_SELECTOR, 'label[id^="org-1-web-"] input', wait_for="presence"
            )
            for checkbox in web_checkboxes:
                self.assertTrue(checkbox.is_selected())
                self.assertEqual(NotificationSetting.objects.get(pk=pk).web, True)

        with self.subTest("Enabling single email notification"):
            first_org_email_checkbox = self.find_element(By.ID, "org-1-email-1")
            first_org_email_checkbox.click()
            input = first_org_email_checkbox.find_element(By.TAG_NAME, "input")
            self.assertTrue(input.is_selected())
            self.assertEqual(
                NotificationSetting.objects.get(
                    pk=input.get_attribute("data-pk")
                ).email,
                True,
            )

    def test_empty_notification_preference_page(self):
        # Delete all organizations
        Organization.objects.all().delete()

        self.login()
        self.open(reverse("notifications:notification_preference"))

        no_organizations_element = self.wait_for_visibility(
            By.CLASS_NAME, "no-organizations"
        )
        self.assertEqual(
            no_organizations_element.text,
            "No organizations available.",
        )

    def test_organization_admin_notification_settings(self):
        """Test the organization-settings.js functionality in Django admin"""
        # Create an organization
        org = self._create_org(name="Test Organization")

        # Login as admin
        self.login()

        # Navigate to organization change page
        org_change_url = reverse(
            f"admin:{self.users_app_label}_organization_change", args=(org.pk,)
        )
        self.open(org_change_url)

        # Scroll to the bottom of the page to find notification settings
        self.web_driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);"
        )

        # Wait for the notification settings section to be visible
        web_field = Select(
            self.wait_for_visibility(By.CSS_SELECTOR, "#id_notification_settings-0-web")
        )
        email_field = Select(
            self.wait_for_visibility(
                By.CSS_SELECTOR, "#id_notification_settings-0-email"
            )
        )

        with self.subTest("Test initial state - both fields should be enabled"):
            # Check initial values - both should be set to True
            self.assertEqual(
                web_field.first_selected_option.get_attribute("value"), "True"
            )
            self.assertEqual(
                email_field.first_selected_option.get_attribute("value"), "True"
            )

        with self.subTest(
            "Test disabling web notifications disables email notifications"
        ):
            # Select "False" for web notifications using Select object
            web_field.select_by_value("False")

            # Verify that email field is automatically set to False
            self.assertEqual(
                email_field.first_selected_option.get_attribute("value"), "False"
            )

        with self.subTest(
            "Test enabling email notifications enables web notifications"
        ):
            # First, verify email is currently False
            self.assertEqual(
                email_field.first_selected_option.get_attribute("value"), "False"
            )

            # Select "True" for email notifications using Select object
            email_field.select_by_value("True")

            # Verify that web field is automatically set to True
            self.assertEqual(
                web_field.first_selected_option.get_attribute("value"), "True"
            )

        with self.subTest("Test setting web to False again after email was enabled"):
            # Disable web notifications again using Select object
            web_field.select_by_value("False")

            # Verify that email field is automatically set to False
            self.assertEqual(
                email_field.first_selected_option.get_attribute("value"), "False"
            )

        with self.subTest("Test saving the form updates the database"):
            # Set web to True and email to True for final test
            web_field.select_by_value("True")
            # Email should automatically be set to True when web is True
            self.assertEqual(
                email_field.first_selected_option.get_attribute("value"), "False"
            )

            # Save the form by clicking the Save button
            save_button = self.find_element(By.CSS_SELECTOR, 'input[name="_continue"]')
            save_button.click()

            # Wait for the page to reload
            self.wait_for_visibility(By.CSS_SELECTOR, ".success")

            # Verify the object was updated in the database
            org.refresh_from_db()
            org_settings = org.notification_settings
            self.assertEqual(org_settings.web, True)
            self.assertEqual(org_settings.email, False)
