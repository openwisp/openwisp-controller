from django.utils.translation import gettext_lazy as _
from geoip2 import errors
from openwisp_notifications.signals import notify
from swapper import load_model

from .. import settings as app_settings

MESSAGE_MAP = {
    "whois_device_error": {
        "type": "generic_message",
        "level": "error",
        "message": _(
            "Failed to fetch WHOIS details for device"
            " [{notification.target}]({notification.target_link})"
        ),
        "description": _("WHOIS details could not be fetched for ip: {ip_address}."),
    },
}

EXCEPTION_MESSAGES = {
    errors.AddressNotFoundError: _(
        "No WHOIS information found for IP address {ip_address}"
    ),
    errors.AuthenticationError: _(
        "Authentication failed for GeoIP2 service. "
        "Check your OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT and "
        "OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY settings."
    ),
    errors.OutOfQueriesError: _(
        "Your account has run out of queries for the GeoIP2 service."
    ),
    errors.PermissionRequiredError: _(
        "Your account does not have permission to access this service."
    ),
}


def send_whois_task_notification(device, notify_type, actor=None):
    Device = load_model("config", "Device")
    if not isinstance(device, Device):
        device = Device.objects.filter(pk=device).first()
        if not device:
            return
    notify_details = MESSAGE_MAP[notify_type]
    notify.send(
        sender=actor or device,
        target=device,
        action_object=device,
        ip_address=device.last_ip,
        **notify_details,
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
