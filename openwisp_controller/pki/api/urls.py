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
            path('controller/ca/', api_views.ca_list, name='ca_list'),
            path('controller/ca/<str:pk>/', api_views.ca_detail, name='ca_detail'),
            path('controller/ca/<str:pk>/renew/', api_views.ca_renew, name='ca_renew'),
            path(
                'controller/ca/<str:pk>/crl',
                api_views.crl_download,
                name='crl_download',
            ),
            path('controller/cert/', api_views.cert_list, name='cert_list'),
            path(
                'controller/cert/<str:pk>/', api_views.cert_detail, name='cert_detail'
            ),
            path(
                'controller/cert/<str:pk>/revoke/',
                api_views.cert_revoke,
                name='cert_revoke',
            ),
            path(
                'controller/cert/<str:pk>/renew/',
                api_views.cert_renew,
                name='cert_renew',
            ),
        ]
    else:
        return []


urlpatterns = get_pki_api_urls(api_views)
