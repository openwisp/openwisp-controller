from openwisp_notifications.utils import _get_object_link

from openwisp_controller.config import settings as config_app_settings
from openwisp_controller.config.whois.service import WHOISService


def check_estimate_location_configured(org_id: str):
    if not org_id:
        return False
    if not config_app_settings.WHOIS_CONFIGURED:
        return False
    org_settings = WHOISService.get_org_config_settings(org_id=org_id)
    return getattr(
        org_settings,
        "estimated_location_enabled",
        config_app_settings.ESTIMATED_LOCATION_ENABLED,
    )


def get_device_location_notification_target_url(obj, field, absolute_url=True):
    url = _get_object_link(obj._related_object(field), absolute_url)
    return f"{url}#devicelocation-group"
