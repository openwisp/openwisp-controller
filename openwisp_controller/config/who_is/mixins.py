from .. import settings as app_settings
from .serializers import WhoIsSerializer


class WhoIsMixin:
    """Mixin to add WhoIs information to the device representation."""

    _who_is_serializer_class = WhoIsSerializer

    def to_representation(self, instance):
        data = super().to_representation(instance)
        org_config = instance._get_organization__config_settings()
        if app_settings.WHO_IS_CONFIGURED and org_config.who_is_enabled:
            data["who_is_info"] = self.get_who_is_info(instance)
        return data

    def get_who_is_info(self, obj):
        if not obj.last_ip:
            return None
        who_is_obj = obj.who_is_service.get_device_who_is_info()
        if not who_is_obj:
            return None
        return self._who_is_serializer_class(who_is_obj).data
