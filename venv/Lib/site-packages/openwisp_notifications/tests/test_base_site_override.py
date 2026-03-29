from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class TestBaseSiteOverride(TestCase):
    """
    Checks that the notification widget and its assets
    are only shown on admin and notifications pages,
    and not on unrelated pages like allauth login.
    """

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
        )

    def test_admin_page_includes_notification_widget_and_assets(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:index"))
        content = response.content.decode()

        self.assertContains(response, 'id="openwisp_notifications"')
        self.assertContains(response, "openwisp-notifications/css/notifications.css")
        self.assertIn("admin/js/vendor/jquery/jquery.min.js", content)
        self.assertContains(
            response, "openwisp-notifications/js/vendor/reconnecting-websocket.min.js"
        )
        self.assertContains(response, "openwisp-notifications/js/notifications.js")
        self.assertContains(
            response,
            'class="ow-overlay ow-overlay-notification ow-overlay-inner ow-hide"',
        )

    def test_notifications_page_includes_notification_widget_and_assets(self):
        self.client.force_login(self.admin)
        url = reverse("notifications:notification_preference")
        response = self.client.get(url)
        content = response.content.decode()

        self.assertContains(response, 'id="openwisp_notifications"')
        self.assertContains(response, "openwisp-notifications/css/notifications.css")
        self.assertIn("admin/js/vendor/jquery/jquery.min.js", content)
        self.assertContains(
            response, "openwisp-notifications/js/vendor/reconnecting-websocket.min.js"
        )
        self.assertContains(response, "openwisp-notifications/js/notifications.js")
        self.assertContains(
            response,
            'class="ow-overlay ow-overlay-notification ow-overlay-inner ow-hide"',
        )

    def test_allauth_pages_exclude_notification_widget_and_assets(self):
        response = self.client.get(reverse("account_login"))
        content = response.content.decode()

        self.assertNotContains(response, 'id="openwisp_notifications"')
        self.assertNotIn("openwisp-notifications/css/notifications.css", content)
        self.assertNotIn("admin/js/vendor/jquery/jquery.min.js", content)
        self.assertNotIn(
            "openwisp-notifications/js/vendor/reconnecting-websocket.min.js", content
        )
        self.assertNotIn("openwisp-notifications/js/notifications.js", content)
        self.assertNotIn(
            'class="ow-overlay ow-overlay-notification ow-overlay-inner ow-hide"',
            content,
        )
