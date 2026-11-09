from django.urls import path

from . import views

app_name = "openwisp_controller"


def get_api_urls(api_views=views):
    """
    returns:: all the API urls of the connection app
    """

    def get_view(name):
        """Fall back to the standard view when a custom view is unavailable."""
        return getattr(api_views, name, getattr(views, name))

    return [
        path(
            "api/v1/controller/device/<uuid:device_id>/command/",
            get_view("command_list_create_view"),
            name="device_command_list",
        ),
        path(
            "api/v1/controller/device/<uuid:device_id>/command/<uuid:pk>/",
            get_view("command_details_view"),
            name="device_command_details",
        ),
        path(
            "api/v1/controller/credential/",
            get_view("credential_list_create_view"),
            name="credential_list",
        ),
        path(
            "api/v1/controller/credential/<uuid:pk>/",
            get_view("credential_detail_view"),
            name="credential_detail",
        ),
        path(
            "api/v1/controller/device/<uuid:device_id>/connection/",
            get_view("deviceconnection_list_create_view"),
            name="deviceconnection_list",
        ),
        path(
            "api/v1/controller/device/<uuid:device_id>/connection/<uuid:pk>/",
            get_view("deviceconnection_detail_view"),
            name="deviceconnection_detail",
        ),
    ]


urlpatterns = get_api_urls()
