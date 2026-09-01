from types import SimpleNamespace

from django.test import SimpleTestCase

from openwisp_controller.pki.api import views
from openwisp_controller.pki.api.urls import get_pki_api_urls


class TestApiUrls(SimpleTestCase):
    def test_get_pki_api_urls_uses_overrides_and_default_fallbacks(self):
        def custom_view():
            return None

        view_names = {
            "ca_list": "ca_list",
            "ca_detail": "ca_detail",
            "ca_renew": "ca_renew",
            "crl_download": "crl_download",
            "cert_list": "cert_list",
            "cert_detail": "cert_detail",
            "cert_revoke": "cert_revoke",
            "cert_renew": "cert_renew",
        }
        custom_views = SimpleNamespace(
            **{
                view_name: custom_view
                for view_name in view_names.values()
                if view_name != "crl_download"
            }
        )
        callbacks = {
            pattern.name: pattern.callback for pattern in get_pki_api_urls(custom_views)
        }

        for url_name, view_name in view_names.items():
            with self.subTest(url_name=url_name):
                expected = (
                    views.crl_download if view_name == "crl_download" else custom_view
                )
                self.assertIs(callbacks[url_name], expected)

        default_callbacks = {
            pattern.name: pattern.callback for pattern in get_pki_api_urls()
        }

        for url_name, view_name in view_names.items():
            with self.subTest(url_name=url_name, custom=False):
                self.assertIs(default_callbacks[url_name], getattr(views, view_name))
