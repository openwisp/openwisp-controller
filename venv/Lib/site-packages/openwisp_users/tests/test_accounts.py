import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now, timedelta

from .. import settings as app_settings
from .utils import TestOrganizationMixin

User = get_user_model()


class TestAccountView(TestOrganizationMixin, TestCase):
    def _login_user(self, username="tester", password="tester"):
        response = self.client.post(
            reverse("account_login"),
            data={"login": username, "password": password},
            follow=True,
        )
        return response

    @patch.object(app_settings, "USER_PASSWORD_EXPIRATION", 30)
    def test_password_expired_user_logins(self):
        self._create_org_user()
        User.objects.update(password_updated=now() - timedelta(days=60))
        response = self._login_user()
        self.assertContains(
            response,
            (
                '<ul class="messagelist">\n'
                '<li class="success">Successfully signed in as tester.</li>\n\n'
                '<li class="warning">Your password has expired, please update '
                "your password.</li>\n</ul>"
            ),
            html=True,
        )
        self.assertEqual(
            response.request.get("PATH_INFO"), reverse("account_change_password")
        )
        # Password expired users can browse accounts views
        self.assertContains(
            response, '<label for="id_oldpassword">Current Password:</label>'
        )
        self.assertContains(response, '<label for="id_password1">New Password:</label>')

    def _test_expired_user_password_reset(self, user):
        User.objects.update(password_updated=now() - timedelta(days=60))
        user.refresh_from_db()
        self.assertEqual(user.has_password_expired(), True)
        response = self.client.post(
            reverse(
                "account_reset_password",
            ),
            data={"email": user.email},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.request.get("PATH_INFO"), reverse("account_reset_password_done")
        )
        self.assertContains(response, "We have sent you an email")
        email = mail.outbox.pop()
        password_reset_url = re.search(r"https?://[^\s]+", email.body).group(0)
        response = self.client.get(
            password_reset_url,
        )
        response = self.client.post(
            response.url,
            data={"password1": "newpassword", "password2": "newpassword"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.request.get("PATH_INFO"),
            reverse("account_reset_password_from_key_done"),
        )

    @patch.object(app_settings, "USER_PASSWORD_EXPIRATION", 30)
    def test_password_expired_user_reset_password(self):
        user = self._create_org_user().user
        self._test_expired_user_password_reset(user)

    @patch.object(app_settings, "USER_PASSWORD_EXPIRATION", 30)
    def test_password_expired_user_reset_password_after_login(self):
        user = self._create_org_user().user
        self._login_user()
        self._test_expired_user_password_reset(user)

    def _test_login_flow(self):
        self._create_org_user()
        User.objects.update(password_updated=now() - timedelta(days=60))
        response = self._login_user()
        self.assertContains(
            response,
            (
                '<ul class="messagelist">\n'
                '<li class="success">Successfully signed in as tester.</li>\n</ul>'
            ),
            html=True,
        )
        self.assertNotContains(
            response,
            (
                '<li class="warning">Your password has expired, please update '
                "your password at http://testserver/accounts/password/change/</li>"
            ),
        )

    @patch.object(app_settings, "USER_PASSWORD_EXPIRATION", 0)
    def test_user_login_password_expiration_disabled(self):
        self._test_login_flow()

    @patch.object(app_settings, "USER_PASSWORD_EXPIRATION", 90)
    def test_user_login_password_expiration_enabled(self):
        self._test_login_flow()

    def test_redirection_to_success_page_after_password_update(self):
        user = self._create_operator()
        self.client.force_login(user)
        response = self.client.post(
            reverse("account_change_password"),
            data={
                "oldpassword": "tester",
                "password1": "newpassword",
                "password2": "newpassword",
            },
            follow=True,
        )
        self.assertContains(response, "Your password has been changed successfully.")
        self.assertContains(response, "This web page can be closed.")

    def test_inactive_user_login(self):
        self._create_org_user()
        User.objects.update(is_active=False)
        response = self._login_user()
        self.assertContains(
            response, "The username and/or password you specified are not correct."
        )

    def test_social_login_user_change_password(self):
        """
        Tests the scenario where a user registers with social login
        and then accesses the change password view.
        """
        # This test simulates the scenario where a user signs up using
        # social login. Social login users do not set a password, so to
        # verify this behavior, we set an unusable password to the user
        # object.
        user = self._create_org_user().user
        user.set_unusable_password()
        user.save()
        self.client.force_login(user)
        response = self.client.get(reverse("account_change_password"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            (
                "<h1>You cannot change your password from this application because"
                " your account is linked to a third-party authentication provider.</h1>"
                "<h1>Please visit the provider's website to manage your password.</h1>"
                "<h1>This web page can be closed.</h1>"
            ),
            html=True,
        )
