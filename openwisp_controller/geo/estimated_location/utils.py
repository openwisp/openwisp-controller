from django.utils.translation import gettext_lazy as _

from openwisp_controller.config.whois.utils import MESSAGE_MAP

# Mutating the existing MESSAGE_MAP to include estimated location messages
MESSAGE_MAP.update(
    {
        "estimated_location_error": {
            "level": "error",
            "type": "estimated_location_info",
            "message": _(
                "Unable to create estimated location for device "
                "[{notification.target}]({notification.target_link}). "
                "Please assign/create a location manually."
            ),
            "description": _("Multiple devices found for IP: {ip_address}"),
        },
        "estimated_location_created": {
            "type": "estimated_location_info",
            "level": "info",
            "message": _(
                "Estimated location [{notification.actor}]({notification.actor_link})"
                " for device"
                " [{notification.target}]({notification.target_link})"
                " {notification.verb} successfully."
            ),
            "description": _("Geographic coordinates inferred from IP: {ip_address}"),
        },
        "estimated_location_updated": {
            "type": "estimated_location_info",
            "level": "info",
            "message": _(
                "Estimated location [{notification.actor}]({notification.actor_link})"
                " for device"
                " [{notification.target}]({notification.target_link})"
                " updated successfully."
            ),
            "description": _("Geographic coordinates updated for IP: {ip_address}"),
        },
    }
)


def get_device_location_notification_target_url(obj, field, absolute_url=True):
    # importing here to avoid "AppRegistryNotReady"
    from openwisp_notifications.utils import _get_object_link

    url = _get_object_link(obj._related_object(field), absolute_url)
    return f"{url}#devicelocation-group"
