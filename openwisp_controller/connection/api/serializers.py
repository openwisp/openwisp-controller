from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from swapper import load_model

from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer

from ...serializers import BaseSerializer

Command = load_model("connection", "Command")
DeviceConnection = load_model("connection", "DeviceConnection")
Credentials = load_model("connection", "Credentials")
Device = load_model("config", "Device")


class ValidatedDeviceFieldSerializer(ValidatedModelSerializer):
    def validate(self, data):
        # Add "device_id" to the data for validation
        data["device_id"] = self.context["device_id"]
        return super().validate(data)


class CommandSerializer(ValidatedDeviceFieldSerializer):
    input = serializers.JSONField(
        allow_null=True,
        help_text=mark_safe(
            _(
                "JSON object containing the command input data. "
                "The structure of this object depends on the command type. "
                'Refer to the <a href="https://openwisp.io/docs/dev/controller/'
                'user/rest-api.html#execute-a-command-on-a-device" target="_blank">'
                "OpenWISP documentation</a> for details."
            )
        ),
    )
    device = serializers.PrimaryKeyRelatedField(
        read_only=True, pk_field=serializers.UUIDField(format="hex_verbose")
    )
    connection = serializers.PrimaryKeyRelatedField(
        allow_null=True,
        queryset=DeviceConnection.objects.all(),
        required=False,
        pk_field=serializers.UUIDField(format="hex_verbose"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # show only connections and command types available for the device
        if device_id := self.context.get("device_id"):
            self.fields["connection"].queryset = self.fields[
                "connection"
            ].queryset.filter(device_id=device_id)
            device = Device.objects.only("organization_id", "id").get(pk=device_id)
            # filter command types based on the device's organization
            self.fields["type"].choices = Command.get_org_allowed_commands(
                device.organization_id
            )

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr["type"] = instance.get_type_display()
        repr["input"] = instance.input_data
        return repr

    class Meta:
        model = Command
        fields = "__all__"
        read_only_fields = [
            "device",
            "output",
            "status",
            "created",
            "modified",
        ]


class CredentialSerializer(BaseSerializer):
    params = serializers.JSONField()

    class Meta:
        model = Credentials
        fields = (
            "id",
            "connector",
            "name",
            "organization",
            "auto_add",
            "params",
            "created",
            "modified",
        )
        read_only_fields = ("created", "modified")


class DeviceConnectionSerializer(
    FilterSerializerByOrgManaged, ValidatedDeviceFieldSerializer
):
    class Meta:
        model = DeviceConnection
        fields = (
            "id",
            "credentials",
            "update_strategy",
            "enabled",
            "is_working",
            "failure_reason",
            "last_attempt",
            "created",
            "modified",
        )
        extra_kwargs = {
            "last_attempt": {"read_only": True},
            "enabled": {"initial": True},
            "is_working": {"read_only": True},
        }
        read_only_fields = ("created", "modified")
