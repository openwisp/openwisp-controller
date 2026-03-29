from asgiref.sync import async_to_sync
from channels import layers
from django.core.cache import cache
from django.utils.timezone import now, timedelta

from openwisp_notifications.api.serializers import NotFound, NotificationListSerializer
from openwisp_notifications.utils import normalize_unread_count

from .. import settings as app_settings
from ..swapper import load_model

Notification = load_model("Notification")


def user_in_notification_storm(user):
    """
    A user is affected by notifications storm if any of short term
    or long term check passes. The checks are configured by
    "OPENWISP_NOTIFICATIONS_NOTIFICATION_STORM_PREVENTION" setting.
    If the user is found to be affected by a notification storm,
    the value of this function is cached for 60 seconds.
    """
    in_notification_storm = cache.get(f"ow-noti-storm-{user.pk}", False)
    if in_notification_storm:
        return True
    if (
        user.notifications.filter(
            timestamp__gte=now()
            - timedelta(
                seconds=app_settings.NOTIFICATION_STORM_PREVENTION[
                    "short_term_time_period"
                ]
            )
        ).count()
        > app_settings.NOTIFICATION_STORM_PREVENTION["short_term_notification_count"]
    ):
        in_notification_storm = True
    elif (
        user.notifications.filter(
            timestamp__gte=now()
            - timedelta(
                seconds=app_settings.NOTIFICATION_STORM_PREVENTION[
                    "long_term_time_period"
                ]
            )
        ).count()
        > app_settings.NOTIFICATION_STORM_PREVENTION["long_term_notification_count"]
    ):
        in_notification_storm = True
    if in_notification_storm:
        cache.set(f"ow-noti-storm-{user.pk}", True, 60)
    return in_notification_storm


def notification_update_handler(reload_widget=False, notification=None, recipient=None):
    channel_layer = layers.get_channel_layer()
    try:
        assert notification is not None
        notification = NotificationListSerializer(notification).data
    except (NotFound, AssertionError):
        pass
    async_to_sync(channel_layer.group_send)(
        f"ow-notification-{recipient.pk}",
        {
            "type": "send.updates",
            "reload_widget": reload_widget,
            "notification": notification,
            "recipient": str(recipient.pk),
            "in_notification_storm": user_in_notification_storm(recipient),
            "notification_count": normalize_unread_count(
                recipient.notifications.unread().count()
            ),
        },
    )
