from django.urls import path

from . import views as api_views

app_name = "openwisp_controller"


def get_api_urls(api_views):
    """
    returns:: all the API urls of the config app
    """
    return [
        path(
            "api/v1/controller/device/<uuid:device_id>/command/",
            api_views.command_list_create_view,
            name="device_command_list",
        ),
        path(
            "api/v1/controller/device/<uuid:device_id>/command/<uuid:pk>/",
            api_views.command_details_view,
            name="device_command_details",
        ),
        path(
            "api/v1/controller/credential/",
            api_views.credential_list_create_view,
            name="credential_list",
        ),
        path(
            "api/v1/controller/credential/<uuid:pk>/",
            api_views.credential_detail_view,
            name="credential_detail",
        ),
        path(
            "api/v1/controller/device/<uuid:device_id>/connection/",
            api_views.deviceconnection_list_create_view,
            name="deviceconnection_list",
        ),
        path(
            "api/v1/controller/device/<uuid:device_id>/connection/<uuid:pk>/",
            api_views.deviceconnection_details_view,
            name="deviceconnection_detail",
        ),
    ]


urlpatterns = get_api_urls(api_views)
