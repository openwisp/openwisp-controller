from .. import settings as app_settings
from .serializers import WHOISSerializer


class WHOISMixin:
    """Mixin to add WHOIS information to the device representation."""

    _whois_serializer_class = WHOISSerializer

    def to_representation(self, instance):
        data = super().to_representation(instance)
        org_config = instance._get_organization__config_settings()
        if app_settings.WHOIS_CONFIGURED and org_config.whois_enabled:
            data["whois_info"] = self.get_whois_info(instance)
        return data

    def get_whois_info(self, obj):
        if not obj.last_ip:
            return None
        whois_obj = obj.whois_service.get_device_whois_info()
        if not whois_obj:
            return None
        return self._whois_serializer_class(whois_obj).data
