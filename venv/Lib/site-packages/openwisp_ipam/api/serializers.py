from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer
from rest_framework import serializers
from swapper import load_model

IpAddress = load_model("openwisp_ipam", "IpAddress")
Subnet = load_model("openwisp_ipam", "Subnet")


class IpRequestSerializer(ValidatedModelSerializer):
    class Meta:
        model = IpAddress
        fields = ("subnet", "description")
        read_only_fields = ("created", "modified")


class IpAddressSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    class Meta:
        model = IpAddress
        fields = "__all__"
        read_only_fields = ("created", "modified")


class SubnetSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    class Meta:
        model = Subnet
        fields = "__all__"
        read_only_fields = ("created", "modified")


class ImportSubnetSerializer(serializers.Serializer):
    csvfile = serializers.FileField()


class HostsResponseSerializer(serializers.Serializer):
    address = serializers.CharField()
    used = serializers.BooleanField()
