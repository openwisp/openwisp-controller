from openwisp_notifications.utils import _get_object_link


def get_connection_working_notification_target_url(obj, field, absolute_url=True):
    url = _get_object_link(obj._related_object(field), absolute_url)
    return f'{url}#deviceconnection_set-group'
