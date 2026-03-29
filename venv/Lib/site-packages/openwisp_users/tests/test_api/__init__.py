from django.test import TestCase
from django.urls import reverse

from openwisp_users.tests.utils import TestMultitenantAdminMixin


class AuthenticationMixin:
    def _obtain_auth_token(self, username="operator", password="tester"):
        params = {"username": username, "password": password}
        url = reverse("users:user_auth_token")
        response = self.client.post(url, params)
        return response.data["token"]


class APITestCase(TestMultitenantAdminMixin, AuthenticationMixin, TestCase):
    pass
