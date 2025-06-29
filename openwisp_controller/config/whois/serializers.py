from rest_framework import serializers
from swapper import load_model

WhoIsInfo = load_model("config", "WhoIsInfo")


class BriefWhoIsSerializer(serializers.ModelSerializer):
    """
    Serializer for brief representation of WhoIs model.
    """

    country = serializers.CharField(source="address.country", read_only=True)

    class Meta:
        model = WhoIsInfo
        fields = ("isp", "country", "ip_address")


class WhoIsSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed representation of WhoIs model.
    """

    address = serializers.JSONField()

    class Meta:
        model = WhoIsInfo
        fields = "__all__"
