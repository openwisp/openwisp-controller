from django.conf import settings
from django.urls import path

from . import download_views as api_download_views
from . import views as api_views

app_name = "openwisp_controller"


def get_api_urls(api_views):
    """
    returns:: all the API urls of the config app
    """
    if getattr(settings, "OPENWISP_CONTROLLER_API", True):
        return [
            path(
                "controller/template/",
                api_views.template_list,
                name="template_list",
            ),
            path(
                "controller/template/<uuid:pk>/",
                api_views.template_detail,
                name="template_detail",
            ),
            path(
                "controller/template/<uuid:pk>/configuration/",
                api_download_views.download_template_config,
                name="download_template_config",
            ),
            path(
                "controller/vpn/",
                api_views.vpn_list,
                name="vpn_list",
            ),
            path(
                "controller/vpn/<uuid:pk>/",
                api_views.vpn_detail,
                name="vpn_detail",
            ),
            path(
                "controller/vpn/<uuid:pk>/configuration/",
                api_download_views.download_vpn_config,
                name="download_vpn_config",
            ),
            path(
                "controller/device/",
                api_views.device_list,
                name="device_list",
            ),
            path(
                "controller/device/<uuid:pk>/",
                api_views.device_detail,
                name="device_detail",
            ),
            path(
                "controller/device/<uuid:pk>/activate/",
                api_views.device_activate,
                name="device_activate",
            ),
            path(
                "controller/device/<uuid:pk>/deactivate/",
                api_views.device_deactivate,
                name="device_deactivate",
            ),
            path(
                "controller/group/",
                api_views.devicegroup_list,
                name="devicegroup_list",
            ),
            path(
                "controller/group/<uuid:pk>/",
                api_views.devicegroup_detail,
                name="devicegroup_detail",
            ),
            path(
                ("controller/cert/<str:common_name>/group/"),
                api_views.devicegroup_commonname,
                name="devicegroup_x509_commonname",
            ),
            path(
                "controller/device/<uuid:pk>/configuration/",
                api_download_views.download_device_config,
                name="download_device_config",
            ),
            path(
                'controller/reversion/',
                api_views.reversion_list,
                name='reversion_list',
            ),
            path(
                'controller/reversion/<str:pk>/',
                api_views.reversion_detail,
                name='reversion_detail',
            ),
            path(
                'controller/reversion/<str:pk>/restore/',
                api_views.reversion_restore,
                name='reversion_restore',
            ),
        ]
    else:
        return []


urlpatterns = get_api_urls(api_views)
