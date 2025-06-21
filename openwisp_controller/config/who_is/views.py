from django.http import HttpResponse, JsonResponse
from swapper import load_model

from .. import settings as app_settings
from ..utils import get_object_or_404
from .service import WhoIsService

Device = load_model("config", "Device")


def get_who_is_info(request):
    if not app_settings.WHO_IS_CONFIGURED:
        return HttpResponse(status=404)
    device_pk = request.GET.get("device_id")
    device = get_object_or_404(Device, pk=device_pk)
    who_is_obj = WhoIsService(device).get_device_who_is_info()
    data = {
        "ip_address": who_is_obj.ip_address,
        "formatted_address": who_is_obj.formatted_address,
        "address": who_is_obj.address,
        "asn": who_is_obj.asn,
        "isp": who_is_obj.isp,
        "cidr": who_is_obj.cidr,
        "timezone": who_is_obj.timezone,
    }
    return JsonResponse(data)
