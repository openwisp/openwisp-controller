from rest_framework import serializers
from swapper import load_model

WHOISInfo = load_model("config", "WHOISInfo")


class WHOISSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed representation of WHOIS model.
    """

    address = serializers.JSONField()

    class Meta:
        model = WHOISInfo
        fields = "__all__"
