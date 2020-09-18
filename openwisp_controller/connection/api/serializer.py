from rest_framework import serializers
from swapper import load_model

Command = load_model('connection', 'Command')
DeviceConnection = load_model('connection', 'DeviceConnection')


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
