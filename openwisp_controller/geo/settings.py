from django.core.exceptions import ImproperlyConfigured

from ..config import settings as config_settings
from ..settings import get_setting

ESTIMATED_LOCATION_ENABLED = get_setting("ESTIMATED_LOCATION_ENABLED", False)

# Validate that WHOIS is enabled if estimated location is enabled
if ESTIMATED_LOCATION_ENABLED and not config_settings.WHOIS_ENABLED:
    raise ImproperlyConfigured(
        "OPENWISP_CONTROLLER_WHOIS_ENABLED must be set to True before "
        "setting OPENWISP_CONTROLLER_ESTIMATED_LOCATION_ENABLED to True."
    )
