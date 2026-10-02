from django.conf import settings
from django.urls import path

from . import views

app_name = "openwisp_controller"


def get_pki_api_urls(api_views=views):
    """
    returns:: all the API urls of the PKI app
    """

    def get_view(name):
        """Fall back to the standard view when a custom view is unavailable."""
        return getattr(api_views, name, getattr(views, name))

    if getattr(settings, "OPENWISP_CONTROLLER_PKI_API", True):
        return [
            path("controller/ca/", get_view("ca_list"), name="ca_list"),
            path("controller/ca/<int:pk>/", get_view("ca_detail"), name="ca_detail"),
            path(
                "controller/ca/<int:pk>/renew/",
                get_view("ca_renew"),
                name="ca_renew",
            ),
            path(
                "controller/ca/<int:pk>/crl",
                get_view("crl_download"),
                name="crl_download",
            ),
            path("controller/cert/", get_view("cert_list"), name="cert_list"),
            path(
                "controller/cert/<int:pk>/", get_view("cert_detail"), name="cert_detail"
            ),
            path(
                "controller/cert/<int:pk>/revoke/",
                get_view("cert_revoke"),
                name="cert_revoke",
            ),
            path(
                "controller/cert/<int:pk>/renew/",
                get_view("cert_renew"),
                name="cert_renew",
            ),
        ]
    else:
        return []


urlpatterns = get_pki_api_urls()
