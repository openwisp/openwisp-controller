import uuid

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
BatchCommand = load_model("connection", "BatchCommand")


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
    batch_command = serializers.PrimaryKeyRelatedField(
        read_only=True,
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


class BatchCommandExecuteSerializer(
    FilterSerializerByOrgManaged, serializers.ModelSerializer
):
    input = serializers.JSONField(allow_null=True, required=False)
    devices = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Device.objects.all(),
        required=False,
        allow_empty=True,
        pk_field=serializers.UUIDField(format="hex_verbose"),
    )
    execute_all = serializers.BooleanField(required=False, default=False)

    def __init__(self, *args, dry_run=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.dry_run = dry_run
        if dry_run:
            self.fields["type"].required = False
            self.fields["label"].required = False

    class Meta:
        model = BatchCommand
        fields = (
            "organization",
            "type",
            "input",
            "label",
            "notes",
            "devices",
            "group",
            "location",
            "execute_all",
        )
        extra_kwargs = {
            "organization": {"required": False, "allow_null": True},
        }

    def validate(self, data):
        org = data.get("organization")
        devices = data.get("devices")
        group = data.get("group")
        location = data.get("location")
        # For dry-run (GET), default to execute_all=True when no
        # targeting options are provided so a bare GET returns all
        # devices without erroring. When any targeting option is
        # given, respect the user's explicit execute_all value.
        if (
            self.dry_run
            and "execute_all" not in self.initial_data
            and not org
            and not devices
            and not group
            and not location
        ):
            execute_all = True
            data["execute_all"] = True
        else:
            execute_all = data.get("execute_all", False)
        if not org and not self.context["request"].user.is_superuser:
            raise serializers.ValidationError(
                _("Only superusers can execute batch commands without an organization.")
            )
        if not execute_all and not org and not devices and not group and not location:
            raise serializers.ValidationError(
                _(
                    "Specify at least one targeting option "
                    "or set execute_all to true."
                )
            )
        if devices:
            for device in devices:
                if org and device.organization_id != org.id:
                    raise serializers.ValidationError(
                        {
                            "devices": _(
                                "All devices must belong to the same organization."
                            )
                        }
                    )
        # DRF's many=True injects [] for QueryDict even when key is
        # absent remove it so model can distinguish omitted vs explicit [].
        elif "devices" not in self.initial_data and "devices" in data:
            data.pop("devices")
        return data


class BatchCommandSerializer(BaseSerializer):
    device_count = serializers.IntegerField(read_only=True)
    skipped_devices = serializers.JSONField(read_only=True)
    organization = serializers.PrimaryKeyRelatedField(
        read_only=True,
        pk_field=serializers.UUIDField(format="hex_verbose"),
    )
    group = serializers.PrimaryKeyRelatedField(
        read_only=True,
        allow_null=True,
        pk_field=serializers.UUIDField(format="hex_verbose"),
    )
    location = serializers.PrimaryKeyRelatedField(
        read_only=True,
        allow_null=True,
        pk_field=serializers.UUIDField(format="hex_verbose"),
    )

    def _redact_skipped_devices(self, data, request):
        skipped = data.get("skipped_devices", {})
        if not skipped:
            return
        device_pks = list(skipped.keys())
        device_org_map = dict(
            Device.objects.filter(pk__in=device_pks).values_list(
                "pk", "organization__name"
            )
        )
        user_org_ids = set(str(org) for org in request.user.organizations_managed)
        user_org_device_uuids = set(
            str(pk)
            for pk, in Device.objects.filter(
                pk__in=device_pks, organization_id__in=user_org_ids
            ).values_list("pk", flat=True)
        )
        redacted = {}
        for device_pk, errors in skipped.items():
            if device_pk in user_org_device_uuids:
                redacted[device_pk] = errors
            else:
                org_name = device_org_map.get(
                    uuid.UUID(device_pk), "some other organization"
                )
                redacted[f"{org_name} device"] = [
                    f"restricted to {org_name} managers and users"
                ]
        data["skipped_devices"] = redacted

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if (
            instance.organization_id is None
            and request
            and not request.user.is_superuser
        ):
            self._redact_skipped_devices(data, request)
        return data

    class Meta:
        model = BatchCommand
        fields = (
            "id",
            "organization",
            "status",
            "type",
            "input",
            "label",
            "notes",
            "group",
            "location",
            "device_count",
            "skipped_devices",
            "created",
            "modified",
        )
        read_only_fields = (
            "created",
            "modified",
        )


class BatchCommandDetailSerializer(BatchCommandSerializer):
    devices = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=True,
        pk_field=serializers.UUIDField(format="hex_verbose"),
    )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if (
            instance.organization_id is None
            and request
            and not request.user.is_superuser
        ):
            user_org_ids = set(str(org) for org in request.user.organizations_managed)
            device_uuids = data.get("devices", [])
            if device_uuids:
                visible_uuids = set(
                    str(pk)
                    for pk, in Device.objects.filter(
                        pk__in=device_uuids, organization_id__in=user_org_ids
                    ).values_list("pk", flat=True)
                )
                data["devices"] = [u for u in device_uuids if u in visible_uuids]
        return data

    class Meta(BatchCommandSerializer.Meta):
        fields = BatchCommandSerializer.Meta.fields + ("devices",)
