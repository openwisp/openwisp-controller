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
                name='template_list',
            ),
            path(
                'controller/template/<str:pk>/',
                api_views.template_detail,
                name='template_detail',
            ),
            path(
                'controller/template/<str:pk>/configuration/',
                api_views.download_template_config,
                name='download_template_config',
            ),
            path(
                'controller/vpn/',
                api_views.vpn_list,
                name='vpn_list',
            ),
            path(
                'controller/vpn/<str:pk>/',
                api_views.vpn_detail,
                name='vpn_detail',
            ),
            path(
                'controller/vpn/<str:pk>/configuration/',
                api_views.download_vpn_config,
                name='download_vpn_config',
            ),
            path(
                'controller/device/',
                api_views.device_list,
                name='device_list',
            ),
            path(
                'controller/device/<str:pk>/',
                api_views.device_detail,
                name='device_detail',
            ),
            path(
                'controller/group/',
                api_views.devicegroup_list,
                name='devicegroup_list',
            ),
            path(
                'controller/group/<str:pk>/',
                api_views.devicegroup_detail,
                name='devicegroup_detail',
            ),
            path(
                ('controller/cert/<str:common_name>/group/'),
                api_views.devicegroup_commonname,
                name='devicegroup_x509_commonname',
            ),
            path(
                'controller/device/<str:pk>/configuration/',
                api_views.download_device_config,
                name='download_device_config',
            ),
        ]
    else:
        return []


urlpatterns = get_api_urls(api_views)
