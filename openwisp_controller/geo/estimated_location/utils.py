from hashlib import sha256
from unicodedata import normalize

from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from openwisp_notifications.signals import notify
from swapper import load_model

from openwisp_controller.config import settings as config_app_settings

MESSAGE_MAP = {
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


def _normalize_location_value(value):
    return " ".join(normalize("NFKC", str(value or "")).split()).casefold()


def _get_estimated_location_state(whois):
    provider = _normalize_location_value(whois.isp) or _normalize_location_value(
        whois.asn
    )
    if not provider:
        provider = whois.ip_address
    address = whois.address
    city = _normalize_location_value(address.get("city"))
    country = _normalize_location_value(address.get("country"))
    postal = _normalize_location_value(address.get("postal"))
    if city and country:
        area = f"{city}:{country}"
    elif postal and country:
        area = f"{postal}:{country}"
    elif whois.coordinates:
        area = f"{whois.coordinates.x:.5f}:{whois.coordinates.y:.5f}"
    else:
        area = whois.ip_address
    return f"{provider}:{area}"


def _get_notification_cache_key(device, whois):
    state = _get_estimated_location_state(whois)
    digest = sha256(f"{device.pk}:{state}".encode()).hexdigest()
    return f"estimated_location_notification:{digest}"


def send_estimated_location_notification(
    device, notify_type, actor=None, ip_address=None, whois=None
):
    Device = load_model("config", "Device")
    if not isinstance(device, Device):
        device = Device.objects.filter(pk=device).first()
        if not device:
            return
    cache_key = None
    if whois and notify_type in {
        "estimated_location_created",
        "estimated_location_updated",
    }:
        cache_key = _get_notification_cache_key(device, whois)
        timeout = config_app_settings.WHOIS_REFRESH_THRESHOLD_DAYS * 24 * 3600
        if not cache.add(cache_key, True, timeout=timeout):
            return
    notify_details = MESSAGE_MAP[notify_type]
    notify.send(
        sender=actor or device,
        target=device,
        action_object=device,
        ip_address=ip_address or device.last_ip,
        **notify_details,
    )


def get_device_location_notification_target_url(obj, field, absolute_url=True):
    # importing here to avoid "AppRegistryNotReady"
    from openwisp_notifications.utils import _get_object_link

    url = _get_object_link(obj._related_object(field), absolute_url)
    return f"{url}#devicelocation-group"


def get_location_defaults_from_whois(whois_obj):
    """
    Create default location data from a WHOISInfo object.

    Args:
        whois_obj: WHOISInfo instance with WHOIS data

    Returns:
        dict: Default values for creating an estimated Location instance
    """
    return {
        "name": whois_obj._location_name,
        "type": "outdoor",
        "is_mobile": False,
        "geometry": whois_obj.coordinates,
        "address": whois_obj.formatted_address,
    }
