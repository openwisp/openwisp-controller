from django.conf import settings
from django.urls import path

from . import download_views, views

app_name = "openwisp_controller"


def get_api_urls(api_views=views):
    """
    returns:: all the API urls of the config app
    """

    def get_view(name):
        """Fall back to the standard view when a custom view is unavailable."""
        for module in (api_views, views, download_views):
            if hasattr(module, name):
                return getattr(module, name)
        raise AttributeError(f"{name} not found in any views module")

    if getattr(settings, "OPENWISP_CONTROLLER_API", True):
        return [
            path(
                "controller/template/",
                get_view("template_list"),
                name="template_list",
            ),
            path(
                "controller/template/<uuid:pk>/",
                get_view("template_detail"),
                name="template_detail",
            ),
            path(
                "controller/template/<uuid:pk>/configuration/",
                get_view("download_template_config"),
                name="download_template_config",
            ),
            path(
                "controller/vpn/",
                get_view("vpn_list"),
                name="vpn_list",
            ),
            path(
                "controller/vpn/<uuid:pk>/",
                get_view("vpn_detail"),
                name="vpn_detail",
            ),
            path(
                "controller/vpn/<uuid:pk>/configuration/",
                get_view("download_vpn_config"),
                name="download_vpn_config",
            ),
            path(
                "controller/device/",
                get_view("device_list"),
                name="device_list",
            ),
            path(
                "controller/device/<uuid:pk>/",
                get_view("device_detail"),
                name="device_detail",
            ),
            path(
                "controller/device/<uuid:pk>/activate/",
                get_view("device_activate"),
                name="device_activate",
            ),
            path(
                "controller/device/<uuid:pk>/deactivate/",
                get_view("device_deactivate"),
                name="device_deactivate",
            ),
            path(
                "controller/group/",
                get_view("devicegroup_list"),
                name="devicegroup_list",
            ),
            path(
                "controller/group/<uuid:pk>/",
                get_view("devicegroup_detail"),
                name="devicegroup_detail",
            ),
            path(
                ("controller/cert/<str:common_name>/group/"),
                get_view("devicegroup_commonname"),
                name="devicegroup_x509_commonname",
            ),
            path(
                "controller/device/<uuid:pk>/configuration/",
                get_view("download_device_config"),
                name="download_device_config",
            ),
        ]
    else:
        return []


urlpatterns = get_api_urls()
