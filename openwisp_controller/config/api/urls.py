from django.conf import settings
from django.urls import path

from . import views as api_views

app_name = 'openwisp_controller'


def get_api_urls(api_views):
    """
    returns:: all the API urls of the config app
    """
    if getattr(settings, 'OPENWISP_CONTROLLER_API', True):
        return [
            path(
                'controller/template/',
                api_views.template_list,
                name='api_template_list',
            ),
            path(
                'controller/template/<str:pk>/',
                api_views.template_detail,
                name='api_template_detail',
            ),
            path(
                'controller/template/<str:pk>/configuration/',
                api_views.download_template_config,
                name='api_download_template_config',
            ),
            path('controller/vpn/', api_views.vpn_list, name='api_vpn_list',),
            path(
                'controller/vpn/<str:pk>/', api_views.vpn_detail, name='api_vpn_detail',
            ),
            path(
                'controller/vpn/<str:pk>/configuration/',
                api_views.download_vpn_config,
                name='api_download_vpn_config',
            ),
            path('controller/device/', api_views.device_list, name='api_device_list',),
            path(
                'controller/device/<str:pk>/',
                api_views.device_detail,
                name='api_device_detail',
            ),
            path(
                'controller/device/<str:pk>/configuration/',
                api_views.download_device_config,
                name='api_download_device_config',
            ),
        ]
    else:
        return []


urlpatterns = get_api_urls(api_views)
