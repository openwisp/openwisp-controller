from types import SimpleNamespace

from django.test import SimpleTestCase

from openwisp_controller.geo.api import views
from openwisp_controller.geo.utils import get_geo_urls


class TestApiUrls(SimpleTestCase):
    def test_get_geo_urls_uses_overrides_and_default_fallbacks(self):
        def custom_view():
            return None

        view_names = {
            "device_coordinates": "device_coordinates",
            "device_location": "device_location",
            "location_geojson": "geojson",
            "location_device_list": "location_device_list",
            "list_floorplan": "list_floorplan",
            "detail_floorplan": "detail_floorplan",
            "list_location": "list_location",
            "detail_location": "detail_location",
            "indoor_coordinates_list": "indoor_coordinates_list",
            "organization_geo_settings": "organization_geo_settings",
        }
        custom_views = SimpleNamespace(
            **{
                view_name: custom_view
                for view_name in view_names.values()
                if view_name != "geojson"
            }
        )
        callbacks = {
            pattern.name: pattern.callback for pattern in get_geo_urls(custom_views)
        }

        for url_name, view_name in view_names.items():
            with self.subTest(url_name=url_name):
                expected = views.geojson if view_name == "geojson" else custom_view
                self.assertIs(callbacks[url_name], expected)
