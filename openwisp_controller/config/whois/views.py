from swapper import load_model

from .. import settings as app_settings
from ..utils import get_object_or_404
from .serializers import WHOISSerializer
from .service import WHOISService

Device = load_model("config", "Device")


def get_whois_info(pk):
    device = get_object_or_404(Device, pk=pk)
    org_settings = device._get_organization__config_settings()
    if not app_settings.WHOIS_CONFIGURED or not org_settings.whois_enabled:
        return None
    whois_obj = WHOISService(device).get_device_whois_info()
    if not whois_obj:
        return None
    data = WHOISSerializer(whois_obj).data
    data["formatted_address"] = whois_obj.formatted_address
    return data
