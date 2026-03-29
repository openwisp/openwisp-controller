from django.templatetags.static import static

from openwisp_notifications import settings as app_settings


def notification_api_settings(request):
    return {
        "OPENWISP_NOTIFICATIONS_HOST": app_settings.HOST,
        "OPENWISP_NOTIFICATIONS_SOUND": static(app_settings.SOUND),
    }
