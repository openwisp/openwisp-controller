from django.utils.translation import gettext as _
from openwisp_notifications.signals import notify
from swapper import load_model

from .. import settings as app_settings

MESSAGE_MAP = {
    "device_error": {
        "message": _(
            "Failed to fetch WHOIS details for device"
            " [{notification.target}]({notification.target_link})"
        ),
        "description": _("WHOIS details could not be fetched for ip: {ip_address}."),
        "level": "error",
    },
    "location_error": {
        "message": _(
            "Unable to create estimated location for device "
            "[{notification.target}]({notification.target_link}). "
            "Please assign/create a location manually."
        ),
        "description": _("Multiple devices found for IP: {ip_address}"),
        "level": "error",
    },
    "location_created": {
        "message": _(
            "Approximate location [{notification.actor}]({notification.actor_link})"
            " for device"
            " [{notification.target}]({notification.target_link}#devicelocation-group)"
            " created successfully."
        ),
        "description": _("Location created for IP: {ip_address}"),
        "level": "info",
    },
    "location_updated": {
        "message": _(
            "Approximate location [{notification.actor}]({notification.actor_link})"
            " for device"
            " [{notification.target}]({notification.target_link}#devicelocation-group)"
            " updated successfully."
        ),
        "description": _("Location updated for IP: {ip_address}"),
        "level": "info",
    },
}


def send_whois_task_notification(device_pk, notify_type, actor=None):
    Device = load_model("config", "Device")

    device = Device.objects.get(pk=device_pk)
    notify_details = MESSAGE_MAP[notify_type]
    notify.send(
        sender=actor or device,
        type="generic_message",
        target=device,
        action_object=device,
        level=notify_details["level"],
        message=notify_details["message"],
        description=notify_details["description"].format(ip_address=device.last_ip),
    )


def get_whois_info(pk):
    from .serializers import WHOISSerializer
    from .service import WHOISService

    Device = load_model("config", "Device")

    if not app_settings.WHOIS_CONFIGURED or not pk:
        return None
    device = (
        Device.objects.select_related("organization__config_settings")
        .filter(pk=pk)
        .first()
    )
    if not device or not device._get_organization__config_settings().whois_enabled:
        return None
    whois_obj = WHOISService(device).get_device_whois_info()
    if not whois_obj:
        return None
    data = WHOISSerializer(whois_obj).data
    data["formatted_address"] = getattr(whois_obj, "formatted_address", None)
    return data
