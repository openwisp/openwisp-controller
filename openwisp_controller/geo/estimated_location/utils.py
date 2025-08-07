from openwisp_controller.config import settings as config_app_settings
from openwisp_controller.config.whois.service import WHOISService


def check_estimate_location_configured(obj):
    if not obj:
        return False
    if not config_app_settings.WHOIS_CONFIGURED:
        return False
    org_id = obj.organization_id
    org_settings = WHOISService.get_config_settings(org_id=org_id)
    return getattr(
        org_settings,
        "estimated_location_enabled",
        config_app_settings.ESTIMATED_LOCATION_ENABLED,
    )
