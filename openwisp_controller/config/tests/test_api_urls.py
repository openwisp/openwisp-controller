from types import SimpleNamespace

from django.test import SimpleTestCase

from openwisp_controller.config.api import download_views
from openwisp_controller.config.api.urls import get_api_urls


class TestApiUrls(SimpleTestCase):
    def test_get_api_urls_uses_overrides_and_default_fallbacks(self):
        def custom_view():
            return None

        view_names = {
            "template_list": "template_list",
            "template_detail": "template_detail",
            "download_template_config": "download_template_config",
            "vpn_list": "vpn_list",
            "vpn_detail": "vpn_detail",
            "download_vpn_config": "download_vpn_config",
            "device_list": "device_list",
            "device_detail": "device_detail",
            "device_activate": "device_activate",
            "device_deactivate": "device_deactivate",
            "devicegroup_list": "devicegroup_list",
            "devicegroup_detail": "devicegroup_detail",
            "devicegroup_x509_commonname": "devicegroup_commonname",
            "download_device_config": "download_device_config",
        }
        custom_views = SimpleNamespace(
            **{
                view_name: custom_view
                for view_name in view_names.values()
                if view_name != "download_template_config"
            }
        )
        callbacks = {
            pattern.name: pattern.callback for pattern in get_api_urls(custom_views)
        }

        for url_name, view_name in view_names.items():
            with self.subTest(url_name=url_name):
                expected = (
                    download_views.download_template_config
                    if view_name == "download_template_config"
                    else custom_view
                )
                self.assertIs(callbacks[url_name], expected)
