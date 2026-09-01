from types import SimpleNamespace

from django.test import SimpleTestCase

from openwisp_controller.connection.api import views
from openwisp_controller.connection.api.urls import get_api_urls


class TestApiUrls(SimpleTestCase):
    def test_get_api_urls_uses_overrides_and_default_fallbacks(self):
        def custom_view():
            return None

        view_names = {
            "device_command_list": "command_list_create_view",
            "device_command_details": "command_details_view",
            "credential_list": "credential_list_create_view",
            "credential_detail": "credential_detail_view",
            "deviceconnection_list": "deviceconnection_list_create_view",
            "deviceconnection_detail": "deviceconnection_detail_view",
        }
        custom_views = SimpleNamespace(
            **{
                view_name: custom_view
                for view_name in view_names.values()
                if view_name != "command_details_view"
            }
        )
        callbacks = {
            pattern.name: pattern.callback for pattern in get_api_urls(custom_views)
        }

        for url_name, view_name in view_names.items():
            with self.subTest(url_name=url_name):
                expected = (
                    views.command_details_view
                    if view_name == "command_details_view"
                    else custom_view
                )
                self.assertIs(callbacks[url_name], expected)
