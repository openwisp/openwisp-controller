from django.core.exceptions import ImproperlyConfigured

from ..config import settings as config_settings
from ..settings import get_setting

ESTIMATED_LOCATION_ENABLED = get_setting("ESTIMATED_LOCATION_ENABLED", False)

if ESTIMATED_LOCATION_ENABLED:
    # Ensure WHOIS is properly configured (credentials present) when
    # estimated location is enabled. WHOIS_CONFIGURED checks for required
    # credentials like WHOIS_GEOIP_ACCOUNT/WHOIS_GEOIP_KEY.
    if not config_settings.WHOIS_CONFIGURED:
        raise ImproperlyConfigured(
            "OPENWISP_CONTROLLER_WHOIS_ENABLED must be set to True before "
            "setting OPENWISP_CONTROLLER_ESTIMATED_LOCATION_ENABLED to True."
        )
