from django.utils.translation import gettext_lazy as _
from openwisp_notifications.types import register_notification_type
from swapper import load_model

from openwisp_controller.config import settings as config_app_settings

from .service import EstimatedLocationService
from .utils import MESSAGE_MAP


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
            **MESSAGE_MAP["estimated_location_created"],
            "verbose_name": _("Estimated Location INFO"),
            "verb": _("created"),
            "email_subject": _("Estimated location created for {notification.target}"),
            "target_link": (
                "openwisp_controller.geo.estimated_location.utils"
                ".get_device_location_notification_target_url"
            ),
            "email_notification": False,
        },
        models=[Device, Location],
    )


def whois_fetched_handler(sender, whois, updated_fields, device=None, **kwargs):
    """
    Signal handler triggered when WHOIS details are fetched.
    """
    if (
        not updated_fields
        or not device
        or not EstimatedLocationService.check_estimated_location_enabled(
            device.organization_id
        )
    ):
        return
    # the estimated location task should not run if old record is updated
    # and location related fields are not updated
    device_location = getattr(device, "devicelocation", None)
    if (
        device_location
        and device_location.location
        and updated_fields
        and not any(i in updated_fields for i in ["address", "coordinates"])
    ):
        return
    estimated_location_service = EstimatedLocationService(device)
    estimated_location_service.trigger_estimated_location_task(whois.ip_address)
