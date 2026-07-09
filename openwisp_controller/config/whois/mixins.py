from .. import settings as app_settings
from .serializers import WHOISSerializer


class WHOISMixin:
    """Mixin to add WHOIS information to the device representation."""

    serializer_class = WHOISSerializer

    def get_whois_info(self, obj):
        whois_obj = obj.whois_service.get_device_whois_info()
        if not whois_obj:
            return None
        return self.serializer_class(whois_obj).data

    def to_representation(self, obj):
        data = super().to_representation(obj)
        if app_settings.WHOIS_CONFIGURED and obj.whois_service.is_whois_enabled:
            data["whois_info"] = self.get_whois_info(obj)
        return data
