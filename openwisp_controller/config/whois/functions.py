from swapper import load_model

from .. import settings as app_settings
from .serializers import WHOISSerializer
from .service import WHOISService

Device = load_model("config", "Device")


def get_whois_info(pk):
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
