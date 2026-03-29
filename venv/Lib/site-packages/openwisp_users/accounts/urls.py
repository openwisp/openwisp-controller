"""
allauth proxy urls
limits the available URLs of django-all auth
in order to keep sign up related features
disabled (not implemented yet).
"""

from importlib import import_module

from allauth import app_settings
from allauth.account import views
from allauth.socialaccount import providers
from django.urls import include, path, re_path, reverse_lazy
from django.views.generic import RedirectView
from django.views.generic.base import TemplateView

from .views import password_change, password_change_success

redirect_view = RedirectView.as_view(url=reverse_lazy("admin:index"))


urlpatterns = [
    path("signup/", redirect_view, name="account_signup"),
    path("login/", views.login, name="account_login"),
    path("logout/", views.logout, name="account_logout"),
    path("inactive/", views.account_inactive, name="account_inactive"),
    # E-mail
    path(
        "confirm-email/",
        views.email_verification_sent,
        name="account_email_verification_sent",
    ),
    re_path(
        r"^confirm-email/(?P<key>[-:\w]+)/$",
        views.confirm_email,
        name="account_confirm_email",
    ),
    # password change
    path(
        "password/change/",
        password_change,
        name="account_change_password",
    ),
    path(
        "password/change/success/",
        password_change_success,
        name="account_change_password_success",
    ),
    # password reset
    path("password/reset/", views.password_reset, name="account_reset_password"),
    path(
        "password/reset/done/",
        views.password_reset_done,
        name="account_reset_password_done",
    ),
    re_path(
        r"^password/reset/key/(?P<uidb36>[0-9A-Za-z]+)-(?P<key>.+)/$",
        views.password_reset_from_key,
        name="account_reset_password_from_key",
    ),
    path(
        "password/reset/key/done/",
        views.password_reset_from_key_done,
        name="account_reset_password_from_key_done",
    ),
    path(
        "email-verification-success/",
        TemplateView.as_view(template_name="account/email_verification_success.html"),
        name="email_confirmation_success",
    ),
    path(
        "logout-success/",
        TemplateView.as_view(template_name="account/logout_success.html"),
        name="logout_success",
    ),
]

if app_settings.SOCIALACCOUNT_ENABLED:
    urlpatterns += [path("social/", include("allauth.socialaccount.urls"))]

for provider in providers.registry.get_class_list():
    try:
        prov_mod = import_module(provider.get_package() + ".urls")
    except ImportError:
        continue
    prov_urlpatterns = getattr(prov_mod, "urlpatterns", None)
    if prov_urlpatterns:
        urlpatterns += prov_urlpatterns
