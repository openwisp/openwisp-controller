from django.conf import settings
from django.urls import include, path

from . import views


def get_api_urls(api_views=None):
    """
    returns:: all the API urls of the app
    arguments::
        api_views: location for getting API views
    """
    if not api_views:
        api_views = views

    if getattr(settings, 'OPENWISP_CONTROLLER_API', False):
        return [
            path(
                'controller/',
                include(
                    [
                        path(
                            'template/', api_views.template_list, name='template_list',
                        ),
                        path(
                            'template/<str:pk>/',
                            api_views.template_detail,
                            name='template_detail',
                        ),
                        path(
                            'template/<str:pk>/configuration/',
                            api_views.download_template_config,
                            name='download_template_config',
                        ),
                        path('vpn/', api_views.vpn_list, name='vpn_list',),
                        path('vpn/<str:pk>/', api_views.vpn_detail, name='vpn_detail',),
                        path(
                            'vpn/<str:pk>/configuration/',
                            api_views.download_vpn_config,
                            name='download_vpn_config',
                        ),
                        path('device/', api_views.device_list, name='device_list',),
                        path(
                            'device/<str:pk>/',
                            api_views.device_detail,
                            name='device_detail',
                        ),
                        path(
                            'device/<str:pk>/configuration/',
                            api_views.download_device_config,
                            name='download_device_config',
                        ),
                    ]
                ),
            ),
        ]
    else:
        return []
