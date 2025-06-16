import json

from django.http import JsonResponse
from swapper import load_model

from ..utils import get_object_or_404
from .service import WhoIsService

Device = load_model("config", "Device")


def get_who_is_info(request):
    device_pk = request.GET.get("device_id")
    device = get_object_or_404(Device, pk=device_pk)
    who_is_obj = WhoIsService(device).get_device_who_is_info()
    data = {
        "ip_address": who_is_obj.ip_address,
        "address": who_is_obj.get_address,
        "asn": who_is_obj.asn,
        "organization": who_is_obj.organization_name,
        "cidr": who_is_obj.cidr,
        "timezone": who_is_obj.timezone,
        "country_code": who_is_obj.country,
    }
    return JsonResponse(data)
