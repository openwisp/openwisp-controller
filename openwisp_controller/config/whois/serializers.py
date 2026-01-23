from rest_framework import serializers
from swapper import load_model

WHOISInfo = load_model("config", "WHOISInfo")


class BriefWHOISSerializer(serializers.ModelSerializer):
    """
    Serializer for brief representation of WHOIS model.
    """

    country = serializers.CharField(source="address.country", read_only=True)

    class Meta:
        model = WHOISInfo
        fields = ("isp", "country", "ip_address")


class WHOISSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed representation of WHOIS model.
    """

    address = serializers.JSONField()

    class Meta:
        model = WHOISInfo
        fields = "__all__"
