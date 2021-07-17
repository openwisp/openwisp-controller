from rest_framework import serializers
from swapper import load_model

from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer

Command = load_model('connection', 'Command')
DeviceConnection = load_model('connection', 'DeviceConnection')
Credentials = load_model('connection', 'Credentials')
Device = load_model('config', 'Device')


class CommandSerializer(serializers.ModelSerializer):
    input = serializers.JSONField(allow_null=True)
    device = serializers.PrimaryKeyRelatedField(
        read_only=True, pk_field=serializers.UUIDField(format='hex_verbose')
    )
    connection = serializers.PrimaryKeyRelatedField(
        allow_null=True,
        queryset=DeviceConnection.objects.all(),
        required=False,
        pk_field=serializers.UUIDField(format='hex_verbose'),
    )

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr['type'] = instance.get_type_display()
        repr['input'] = instance.input_data
        return repr

    class Meta:
        model = Command
        fields = '__all__'
        read_only_fields = [
            'device',
            'output',
            'status',
            'created',
            'modified',
        ]


class CredentialSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    params = serializers.JSONField()

    class Meta:
        model = Credentials
        fields = (
            'id',
            'connector',
            'name',
            'organization',
            'auto_add',
            'params',
            'created',
            'modified',
        )
        read_only_fields = ('created', 'modified')


class DeviceConnectionSerializer(
    FilterSerializerByOrgManaged, ValidatedModelSerializer
):
    class Meta:
        model = DeviceConnection
        fields = (
            'id',
            'credentials',
            'update_strategy',
            'enabled',
            'is_working',
            'failure_reason',
            'last_attempt',
            'created',
            'modified',
        )
        extra_kwargs = {
            'last_attempt': {'read_only': True},
            'enabled': {'initial': True},
            'is_working': {'read_only': True},
        }
        read_only_fields = ('created', 'modified')

    def validate(self, data):
        data['device'] = Device.objects.get(pk=self.context['device_id'])
        instance = self.instance or self.Meta.model(**data)
        instance.full_clean()
        return data
