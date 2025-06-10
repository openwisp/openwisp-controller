from rest_framework import serializers
from swapper import load_model

WhoIsInfo = load_model("config", "WhoIsInfo")


class BriefWhoIsSerializer(serializers.ModelSerializer):
    """
    Serializer for brief representation of WhoIs model.
    """

    class Meta:
        model = WhoIsInfo
        fields = ("organization_name", "country")


class WhoIsSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed representation of WhoIs model.
    """

    class Meta:
        model = WhoIsInfo
        fields = "__all__"


class WhoIsSerializerMixin(serializers.Serializer):
    """
    Mixin to get related WhoIs information for a device.
    """

    who_is = serializers.SerializerMethodField()

    _who_is_serializer_class = WhoIsSerializer

    def get_who_is(self, obj):
        """
        Fetch WhoIs information for the device.
        """
        if not obj.last_ip:
            return None
        who_is_obj = obj.who_is_service.get_device_who_is_info()
        if not who_is_obj:
            return None
        return self._who_is_serializer_class(who_is_obj).data
