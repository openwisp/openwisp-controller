from django.utils import formats, timezone
from openwisp_notifications.utils import _get_object_link


def format_localized_datetime(value):
    if not value:
        return ""
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return formats.date_format(value, "DATETIME_FORMAT")


def get_connection_working_notification_target_url(obj, field, absolute_url=True):
    url = _get_object_link(obj._related_object(field), absolute_url)
    return f"{url}#deviceconnection_set-group"
