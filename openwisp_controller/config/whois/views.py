from django.http import HttpResponse, JsonResponse
from swapper import load_model

from .. import settings as app_settings
from ..utils import get_object_or_404
from .serializers import WhoIsSerializer
from .service import WhoIsService

Device = load_model("config", "Device")


def get_who_is_info(request):
    device_pk = request.GET.get("device_id")
    device = get_object_or_404(Device, pk=device_pk)
    org_settings = device._get_organization__config_settings()
    if not app_settings.WHO_IS_CONFIGURED or not org_settings.who_is_enabled:
        return HttpResponse(status=404)
    who_is_obj = WhoIsService(device).get_device_who_is_info()
    if not who_is_obj:
        return HttpResponse(status=404)
    data = WhoIsSerializer(who_is_obj).data
    data["formatted_address"] = who_is_obj.formatted_address
    return JsonResponse(data)
