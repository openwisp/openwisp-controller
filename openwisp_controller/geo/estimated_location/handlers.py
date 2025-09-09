from django.utils.translation import gettext_lazy as _
from openwisp_notifications.types import register_notification_type
from swapper import load_model

from openwisp_controller.config import settings as config_app_settings


def register_estimated_location_notification_types():
    """
    Register the notification types used by the Estimated Location module.
    This is necessary to ensure that the notifications are properly configured.
    """
    if not config_app_settings.WHOIS_CONFIGURED:
        return

    Device = load_model("config", "Device")
    Location = load_model("geo", "Location")

    register_notification_type(
        "estimated_location_info",
        {
            "verbose_name": _("Estimated Location INFO"),
            "verb": _("created"),
            "level": "info",
            "email_subject": _(
                "Estimated Location: Created for device {notification.target}"
            ),
            "message": _(
                "Estimated location [{notification.actor}]({notification.actor_link})"
                " for device"
                " [{notification.target}]({notification.target_link})"
                " {notification.verb} successfully."
            ),
            "target_link": (
                "openwisp_controller.geo.estimated_location.utils"
                ".get_device_location_notification_target_url"
            ),
            "email_notification": False,
        },
        models=[Device, Location],
    )
