from django.urls import path

from openwisp_users import settings as app_settings

from . import views


def get_api_urls(api_views=None):
    urlpatterns = []
    if api_views is None:
        api_views = views
    urlpatterns += [
        path(
            "users/organization/",
            views.organization_list,
            name="organization_list",
        ),
        path(
            "users/organization/<str:pk>/",
            views.organization_detail,
            name="organization_detail",
        ),
        path(
            "users/user/",
            views.user_list,
            name="user_list",
        ),
        path("users/user/<str:pk>/", views.user_detail, name="user_detail"),
        path(
            "users/user/<str:pk>/password/",
            views.change_password,
            name="change_password",
        ),
        path(
            "users/user/<str:pk>/email/",
            views.email_list,
            name="email_list",
        ),
        path(
            "users/user/<str:pk>/email/<int:email_id>/",
            views.email_update,
            name="email_update",
        ),
        path("users/group/", views.group_list, name="group_list"),
        path("users/group/<int:pk>/", views.group_detail, name="group_detail"),
    ]
    if app_settings.USERS_AUTH_API:
        urlpatterns += [
            path("users/token/", views.obtain_auth_token, name="user_auth_token")
        ]
    return urlpatterns


urlpatterns = get_api_urls()
