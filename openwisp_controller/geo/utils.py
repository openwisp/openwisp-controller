from django.urls import path

from .api import views


def get_geo_urls(geo_views=views):
    def get_view(name):
        """Fall back to the standard view when a custom view is unavailable."""
        return getattr(geo_views, name, getattr(views, name))

    return [
        path(
            "api/v1/controller/device/<uuid:pk>/coordinates/",
            get_view("device_coordinates"),
            name="device_coordinates",
        ),
        path(
            "api/v1/controller/device/<uuid:pk>/location/",
            get_view("device_location"),
            name="device_location",
        ),
        path(
            "api/v1/controller/location/geojson/",
            get_view("geojson"),
            name="location_geojson",
        ),
        path(
            "api/v1/controller/location/<uuid:pk>/device/",
            get_view("location_device_list"),
            name="location_device_list",
        ),
        path(
            "api/v1/controller/floorplan/",
            get_view("list_floorplan"),
            name="list_floorplan",
        ),
        path(
            "api/v1/controller/floorplan/<uuid:pk>/",
            get_view("detail_floorplan"),
            name="detail_floorplan",
        ),
        path(
            "api/v1/controller/location/",
            get_view("list_location"),
            name="list_location",
        ),
        path(
            "api/v1/controller/location/<uuid:pk>/",
            get_view("detail_location"),
            name="detail_location",
        ),
        path(
            "api/v1/controller/location/<uuid:pk>/indoor-coordinates/",
            get_view("indoor_coordinates_list"),
            name="indoor_coordinates_list",
        ),
        path(
            "api/v1/controller/organization/<uuid:organization_pk>/geo-settings/",
            get_view("organization_geo_settings"),
            name="organization_geo_settings",
        ),
    ]
