import uuid
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.forms.widgets import Media, MediaOrderConflictWarning
from django.test import TestCase, override_settings, tag
from django.urls import reverse

from openwisp_notifications import settings as app_settings
from openwisp_notifications.signals import notify
from openwisp_notifications.swapper import load_model, swapper_load_model
from openwisp_notifications.widgets import _add_object_notification_widget
from openwisp_users.admin import UserAdmin
from openwisp_users.tests.utils import TestMultitenantAdminMixin

from .test_helpers import MessagingRequest

Notification = load_model("Notification")
NotificationSetting = load_model("NotificationSetting")
notification_queryset = Notification.objects.order_by("-timestamp")
Group = swapper_load_model("openwisp_users", "Group")


class MockUser:
    def __init__(self, is_superuser=False):
        self.is_superuser = is_superuser
        self.id = uuid.uuid4()

    def has_perm(self, perm):
        return True

    @property
    def pk(self):
        return self.id


User = get_user_model()
su_request = MessagingRequest()
su_request.user = MockUser(is_superuser=True)

op_request = MessagingRequest()
op_request.user = MockUser(is_superuser=False)


class BaseTestAdmin(TestMultitenantAdminMixin, TestCase):
    def _login_admin(self):
        u = User.objects.create_superuser("admin", "admin", "test@test.com")
        self.client.force_login(u)
        return u

    def setUp(self):
        self.admin = self._login_admin()
        self.notification_options = dict(
            sender=self.admin,
            recipient=self.admin,
            description="Test Notification",
            verb="Test Notification",
            email_subject="Test Email subject",
            url="localhost:8000/admin",
        )
        self.site = AdminSite()

    @property
    def _url(self):
        return reverse("admin:index")

    def _expected_output(self, count=None):
        if count:
            return '<span id="ow-notification-count">{0}</span>'.format(count)
        return 'id="openwisp_notifications">'


class TestAdmin(BaseTestAdmin):
    """
    Tests notifications in admin
    """

    app_label = "openwisp_notifications"
    users_app_label = "openwisp_users"

    def test_zero_notifications(self):
        r = self.client.get(self._url)
        self.assertContains(r, self._expected_output())

    def test_non_zero_notifications(self):
        patched_function = "openwisp_notifications.templatetags.notification_tags._get_user_unread_count"
        with self.subTest("Test UI for less than 100 notifications"):
            with patch(patched_function, return_value=10):
                r = self.client.get(self._url)
                self.assertContains(r, self._expected_output("10"))

        Notification.invalidate_unread_cache(self.admin)

        with self.subTest("Test UI for 99+ notifications"):
            with patch(patched_function, return_value=100):
                r = self.client.get(self._url)
                self.assertContains(r, self._expected_output("99+"))

    def test_cached_value(self):
        self.client.get(self._url)
        cache_key = Notification.count_cache_key(self.admin.pk)
        self.assertEqual(cache.get(cache_key), 0)
        return cache_key

    def test_cached_invalidation(self):
        cache_key = self.test_cached_value()
        notify.send(**self.notification_options)
        self.assertIsNone(cache.get(cache_key))
        self.client.get(self._url)
        self.assertEqual(cache.get(cache_key), 1)

    @tag("skip_prod")
    # This tests depends on the static storage backend of the project.
    # In prod environment, the filenames could get changed due to
    # static minification and cache invalidation. Hence, these tests
    # should not be run on prod environment because they'll fail.
    def test_default_notification_setting(self):
        res = self.client.get(self._url)
        self.assertContains(
            res, "/static/openwisp-notifications/audio/notification_bell.mp3"
        )
        self.assertContains(res, "window.location")

    @tag("skip_prod")
    # For more info, look at TestAdmin.test_default_notification_setting
    @patch.object(
        app_settings,
        "SOUND",
        "/static/notification.mp3",
    )
    def test_notification_sound_setting(self):
        res = self.client.get(self._url)
        self.assertContains(res, "/static/notification.mp3")
        self.assertNotContains(
            res, "/static/openwisp-notifications/audio/notification_bell.mp3"
        )

    @patch.object(
        app_settings,
        "HOST",
        "https://example.com",
    )
    def test_notification_host_setting(self):
        res = self.client.get(self._url)
        self.assertContains(res, "https://example.com")
        self.assertNotContains(res, "window.location")

    def test_login_load_javascript(self):
        self.client.logout()
        response = self.client.get(reverse("admin:login"))
        self.assertNotContains(response, "notifications.js")

    def test_websocket_protocol(self):
        with self.subTest("Test in production environment"):
            response = self.client.get(self._url)
            self.assertContains(response, "wss")

    def test_ignore_notification_widget_add_view(self):
        url = reverse(f"admin:{self.users_app_label}_organization_add")
        response = self.client.get(url)
        self.assertNotContains(response, "owIsChangeForm")

    def test_notification_preferences_button_staff_user(self):
        user = self._create_user(is_staff=True)
        user_admin_page = reverse(
            f"admin:{self.users_app_label}_user_change", args=(user.pk,)
        )
        expected_url = reverse(
            "notifications:user_notification_preference", args=(user.pk,)
        )
        expected_html = (
            f'<a class="button" href="{expected_url}">Notification Preferences</a>'
        )

        # Button appears for staff user
        with self.subTest("Button should appear for staff user"):
            response = self.client.get(user_admin_page)
            self.assertContains(response, expected_html, html=True)

        # Button does not appear for non-staff user
        with self.subTest("Button should not appear for non-staff user"):
            user.is_staff = False
            user.full_clean()
            user.save()
            response = self.client.get(user_admin_page)
            self.assertNotContains(response, expected_html, html=True)


class TestOrganizationNotificationsSettingsAdmin(BaseTestAdmin):
    app_label = "openwisp_notifications"
    users_app_label = "openwisp_users"

    def test_organization_notifications_settings_admin(self):
        org = self._get_org()
        path = reverse(
            f"admin:{self.users_app_label}_organization_change", args=(org.pk,)
        )
        response = self.client.get(path)
        self.assertContains(response, "Notification Settings")
        self.assertContains(
            response,
            "<h3><b>Notification Settings:</b>"
            '<span class="inline_label">'
            f"OrganizationNotificationSettings object ({org.notification_settings.pk})"
            "</span></h3>",
            html=True,
        )
        self.assertNotContains(
            response,
            '<a href="#">Add another Notification Settings</a>',
            html=True,
        )

    def test_permissions(self):
        org = self._get_org()
        org_settings = org.notification_settings
        org_settings.web = True
        org_settings.email = True
        org_settings.full_clean()
        org_settings.save()
        path = reverse(
            f"admin:{self.users_app_label}_organization_change", args=(org.pk,)
        )
        response = self.client.get(path)
        with self.subTest("Operator has read only permissions"):
            operator = self._create_operator(organizations=[org])
            self.client.force_login(operator)
            response = self.client.get(path)
            self.assertContains(response, "Notification Settings")
            self.assertNotContains(
                response,
                '<select name="notification_settings-0-web"',
            )
            self.assertNotContains(
                response,
                '<select name="notification_settings-0-email"',
            )
            self.assertContains(
                response,
                "<label>Web notifications enabled:</label>"
                '<div class="readonly"><img src="/static/admin/img/icon-yes.svg" alt="True"></div>',
                html=True,
            )
            self.assertContains(
                response,
                "<label>Email notifications enabled:</label>"
                '<div class="readonly"><img src="/static/admin/img/icon-yes.svg" alt="True"></div>',
                html=True,
            )

        with self.subTest("Administrator has change permissions"):
            admin = self._create_administrator(organizations=[org])
            self.client.force_login(admin)
            response = self.client.get(path)
            self.assertContains(response, "Notification Settings")
            self.assertContains(
                response,
                '<select name="notification_settings-0-web"',
            )
            self.assertContains(
                response,
                '<select name="notification_settings-0-email"',
            )


@tag("skip_prod")
# For more info, look at TestAdmin.test_default_notification_setting
class TestAdminMedia(BaseTestAdmin):
    """
    Tests notifications admin media
    """

    users_app_label = "openwisp_users"

    def test_jquery_import(self):
        response = self.client.get(self._url)
        self.assertInHTML(
            '<script src="/static/admin/js/jquery.init.js">',
            str(response.content),
            1,
        )
        self.assertInHTML(
            '<script src="/static/admin/js/vendor/jquery/jquery.min.js">',
            str(response.content),
            1,
        )

        response = self.client.get(reverse("admin:sites_site_changelist"))
        self.assertIn(
            "/static/admin/js/jquery.init.js",
            str(response.content),
            1,
        )
        self.assertIn(
            "/static/admin/js/vendor/jquery/jquery.min.js",
            str(response.content),
            1,
        )

    def test_object_notification_setting_empty(self):
        response = self.client.get(
            reverse(f"admin:{self.users_app_label}_user_change", args=(self.admin.pk,))
        )
        self.assertNotContains(
            response, 'src="/static/openwisp-notifications/js/object-notifications.js"'
        )

    @override_settings(
        OPENWISP_NOTIFICATIONS_IGNORE_ENABLED_ADMIN=["openwisp_users.admin.UserAdmin"],
    )
    def test_object_notification_setting_configured(self):
        _add_object_notification_widget()
        response = self.client.get(
            reverse(f"admin:{self.users_app_label}_user_change", args=(self.admin.pk,))
        )
        self.assertContains(
            response,
            'src="/static/openwisp-notifications/js/object-notifications.js"',
            1,
        )

        # If a ModelAdmin already has a Media class
        with self.assertWarns(MediaOrderConflictWarning):
            _add_object_notification_widget()
            response = self.client.get(
                reverse(
                    f"admin:{self.users_app_label}_user_change", args=(self.admin.pk,)
                )
            )

        # If a ModelAdmin has list instances of js and css
        UserAdmin.Media.css = {"all": list()}
        UserAdmin.Media.js = list()
        _add_object_notification_widget()
        response = self.client.get(
            reverse(f"admin:{self.users_app_label}_user_change", args=(self.admin.pk,))
        )

        # If ModelAdmin has empty attributes
        UserAdmin.Media.js = []
        UserAdmin.Media.css = {}
        _add_object_notification_widget()
        response = self.client.get(
            reverse(f"admin:{self.users_app_label}_user_change", args=(self.admin.pk,))
        )
        UserAdmin.Media = Media()
