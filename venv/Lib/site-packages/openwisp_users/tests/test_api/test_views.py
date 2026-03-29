from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from openwisp_users.tests.utils import TestOrganizationMixin


class TestRestFrameworkViews(TestOrganizationMixin, TestCase):
    def setUp(self):
        cache.clear()

    def test_obtain_auth_token(self):
        self._create_user(username="tester", password="tester")
        params = {"username": "tester", "password": "tester"}
        url = reverse("users:user_auth_token")
        r = self.client.post(url, params)
        self.assertIn("token", r.data)

    def test_protected_api_mixin_view(self):
        auth_error = "Authentication credentials were not provided."
        user = self._create_user(username="tester", password="tester")
        path = reverse("users:user_detail", args=(user.pk,))
        response = self.client.get(path)
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
        self.assertEqual(response.data["detail"], auth_error)
        self.assertEqual(response.status_code, 401)
