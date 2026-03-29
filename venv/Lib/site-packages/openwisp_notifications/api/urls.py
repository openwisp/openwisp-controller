from django.urls import path

from openwisp_notifications.api import views

app_name = "openwisp_notifications"


def get_api_urls(api_views=None):
    if not api_views:
        api_views = views
    return [
        path("notification/", api_views.notifications_list, name="notifications_list"),
        path(
            "notification/read/",
            api_views.notifications_read_all,
            name="notifications_read_all",
        ),
        path(
            "notification/<uuid:pk>/",
            api_views.notification_detail,
            name="notification_detail",
        ),
        path(
            "notification/<uuid:pk>/redirect/",
            api_views.notification_read_redirect,
            name="notification_read_redirect",
        ),
        path(
            "user/<uuid:user_id>/user-setting/",
            api_views.notification_setting_list,
            name="user_notification_setting_list",
        ),
        path(
            "user/<uuid:user_id>/user-setting/<uuid:pk>/",
            api_views.notification_setting,
            name="user_notification_setting",
        ),
        path(
            "user/<uuid:user_id>/organization/<uuid:organization_id>/setting/",
            api_views.user_org_notification_setting,
            name="user_org_notification_setting",
        ),
        path(
            "notification/ignore/",
            api_views.ignore_object_notification_list,
            name="ignore_object_notification_list",
        ),
        path(
            "notification/ignore/<str:app_label>/<str:model_name>/<uuid:object_id>/",
            api_views.ignore_object_notification,
            name="ignore_object_notification",
        ),
        path(
            "organization/<uuid:organization_id>/setting/",
            api_views.org_notification_setting,
            name="org_notification_setting",
        ),
        # DEPRECATED
        path(
            "user/user-setting/",
            api_views.notification_setting_list,
            name="notification_setting_list",
        ),
        path(
            "user/user-setting/<uuid:pk>/",
            api_views.notification_setting,
            name="notification_setting",
        ),
    ]
