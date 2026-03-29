from django.urls import include, path

from . import views
from .api.urls import get_api_urls
from .views import notification_preference_view, unsubscribe_view

app_name = "notifications"


def get_urls(api_views=None, social_views=None):
    """
    Returns a list of urlpatterns
    Arguments:
        api_views(optional): views for Notifications API
    """
    urls = [
        path(
            "notifications/resend-verification-email/",
            views.resend_verification_email,
            name="resend_verification_email",
        ),
        path("api/v1/notifications/", include(get_api_urls(api_views))),
        path(
            "notifications/preferences/",
            notification_preference_view,
            name="notification_preference",
        ),
        path(
            "notifications/user/<uuid:pk>/preferences/",
            notification_preference_view,
            name="user_notification_preference",
        ),
        path("notifications/unsubscribe/", unsubscribe_view, name="unsubscribe"),
    ]
    return urls


app_name = "notifications"
urlpatterns = get_urls()
