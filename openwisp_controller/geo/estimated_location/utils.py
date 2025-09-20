from openwisp_notifications.utils import _get_object_link


def get_device_location_notification_target_url(obj, field, absolute_url=True):
    url = _get_object_link(obj._related_object(field), absolute_url)
    return f"{url}#devicelocation-group"
