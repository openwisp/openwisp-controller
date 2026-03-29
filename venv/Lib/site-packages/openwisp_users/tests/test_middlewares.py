from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, modify_settings
from django.urls import reverse
from django.utils.timezone import now, timedelta

from .. import settings as app_settings
from .utils import TestOrganizationMixin

User = get_user_model()


class TestPasswordExpirationMiddleware(TestOrganizationMixin, TestCase):
    @modify_settings(
        MIDDLEWARE={
            "remove": ["openwisp_users.middleware.PasswordExpirationMiddleware"]
        }
    )
    @patch.object(app_settings, "STAFF_USER_PASSWORD_EXPIRATION", 10)
    def test_queries_middleware_absent(self):
        admin = self._create_admin()
        with self.assertNumQueries(2):
            response = self.client.post(
                reverse("admin:login"),
                data={"username": admin.username, "password": "tester"},
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/admin/")
        with self.assertNumQueries(1):
            self.client.force_login(admin)

    @modify_settings(
        MIDDLEWARE={
            "append": ["openwisp_users.middleware.PasswordExpirationMiddleware"]
        }
    )
    @patch.object(app_settings, "STAFF_USER_PASSWORD_EXPIRATION", 10)
    def test_queries_middleware_present(self):
        admin = self._create_admin(password_updated=now().date() - timedelta(days=180))
        with self.assertNumQueries(2):
            response = self.client.post(
                reverse("admin:login"),
                data={"username": admin.username, "password": "tester"},
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/accounts/password/change/?next=/admin/")
        with self.assertNumQueries(1):
            self.client.force_login(admin)
