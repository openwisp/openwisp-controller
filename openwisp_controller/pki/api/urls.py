from django.conf import settings
from django.urls import path

from . import views as api_views

app_name = 'openwisp_controller'


def get_pki_api_urls(api_views):
    """
    returns:: all the API urls of the PKI app
    """
    if getattr(settings, 'OPENWISP_CONTROLLER_PKI_API', True):
        return [
            path('ca/', api_views.ca_list, name='api_ca_list'),
            path('ca/<str:pk>/', api_views.ca_detail, name='api_ca_detail'),
            path(
                'ca/<str:pk>/crl', api_views.crl_download_view, name='api_ca_download'
            ),
            path('cert/', api_views.cert_list, name='api_cert_list'),
            path('cert/<str:pk>/', api_views.cert_detail, name='api_cert_detail'),
        ]
    else:
        return []


urlpatterns = get_pki_api_urls(api_views)
