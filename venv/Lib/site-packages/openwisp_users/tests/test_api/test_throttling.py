from django.core.cache import cache
from django.urls import reverse

from openwisp_users.api.throttling import AuthRateThrottle

from . import APITestCase


class RatelimitTests(APITestCase):
    def setUp(self):
        cache.clear()
        self._create_operator()

    def test_auth_rate_throttle(self):
        AuthRateThrottle.rate = "1/day"
        url = reverse("users:user_auth_token")
        data = {"username": "operator", "password": "tester"}
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 429)
