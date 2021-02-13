import ast
import collections
import json

from rest_framework import serializers
from swapper import load_model

from openwisp_users.api.mixins import FilterSerializerByOrgOwned
from openwisp_utils.api.serializers import ValidatedModelSerializer

Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
Device = load_model('config', 'Device')
Config = load_model('config', 'Config')
TemplateTag = load_model('config', 'TemplateTag')
Organization = load_model('openwisp_users', 'Organization')


class BaseMeta:
    read_only_fields = ['created', 'modified']


class TemplateSerializer(FilterSerializerByOrgOwned, ValidatedModelSerializer):
    config = serializers.JSONField()
    tags = serializers.StringRelatedField(many=True, read_only=True)
    default_values = serializers.JSONField(required=False, default={})

    class Meta(BaseMeta):
        model = Template
        fields = [
            'id',
            'name',
            'tags',
            'organization',
            'type',
            'backend',
            'default',
            'required',
            'default_values',
            'config',
            'created',
            'modified',
        ]


class VpnSerializer(FilterSerializerByOrgOwned, ValidatedModelSerializer):
    config = serializers.JSONField()

    class Meta(BaseMeta):
        model = Vpn
        fields = [
            'id',
            'name',
            'host',
            'organization',
            'key',
            'ca',
            'cert',
            'backend',
            'notes',
            'dh',
            'config',
        ]


class JsonConfigField(serializers.Field):
    def to_representation(self, value):
        return json.loads(json.dumps(value))

    def to_internal_value(self, data):
        if type(data) is str:
            return ast.literal_eval(data)
        else:
            return data


class JsonContextField(serializers.Field):
    def to_representation(self, value):
        return dict(value)

    def to_internal_value(self, data):
        if type(data) is str:
            return ast.literal_eval(data)
        else:
            return data


class DeviceConfigSerializer(serializers.ModelSerializer):
    config = JsonConfigField(
        help_text='''<i>config</i> field in HTML form
        accepts values in dictionary format'''
    )
    context = JsonContextField(
        help_text='''<i>context</i> field in HTML form
        accepts values in dictionary format'''
    )

    class Meta:
        model = Config
        fields = ['backend', 'status', 'templates', 'context', 'config']
        extra_kwargs = {'status': {'read_only': True}}


class DeviceListSerializer(serializers.ModelSerializer):
    config = DeviceConfigSerializer(write_only=True)

    class Meta(BaseMeta):
        model = Device
        fields = [
            'id',
            'name',
            'organization',
            'mac_address',
            'key',
            'last_ip',
            'management_ip',
            'model',
            'os',
            'system',
            'notes',
            'config',
        ]

    def create(self, validated_data):
        config_data = validated_data.pop('config')
        device = Device.objects.create(**validated_data)
        config_templates = [template.pk for template in config_data.pop('templates')]
        config = Config.objects.create(device=device, **config_data)
        config.templates.add(*config_templates)
        return device


class DeviceDetailSerializer(FilterSerializerByOrgOwned, ValidatedModelSerializer):
    config = DeviceConfigSerializer()

    class Meta(BaseMeta):
        model = Device
        fields = DeviceListSerializer.Meta.fields

    def update(self, instance, validated_data):
        config_data = None

        if self.initial_data.get('config.backend') and instance.backend is None:
            new_config_data = dict(validated_data.pop('config'))
            config_templates = [
                template.pk for template in new_config_data.pop('templates')
            ]
            config = Config.objects.create(device=instance, **new_config_data)
            config.templates.add(*config_templates)
            return super().update(instance, validated_data)

        if validated_data.get('config'):
            config_data = validated_data.pop('config')

        if config_data:
            instance.config.backend = config_data.get(
                'backend', instance.config.backend
            )

            new_config_templates = [
                template.pk for template in config_data.get('templates')
            ]
            old_config_templates = [
                template
                for template in instance.config.templates.values_list('pk', flat=True)
            ]
            if new_config_templates != old_config_templates:
                instance.config.templates.clear()
                instance.config.templates.add(*new_config_templates)

            instance.config.context = json.loads(
                json.dumps(config_data.get('context')),
                object_pairs_hook=collections.OrderedDict,
            )
            instance.config.config = json.loads(
                json.dumps(config_data.get('config')),
                object_pairs_hook=collections.OrderedDict,
            )
            instance.config.save()

        return super().update(instance, validated_data)

    # Raise Exception when removing templates flagged as required
    def validate_config(self, value):
        instance = self.instance
        if instance.backend:
            prev_req_templates = [
                required_status
                for required_status in instance.config.templates.values_list(
                    'required', flat=True
                )
                if required_status is True
            ]
            incoming_req_templates = [
                template.required
                for template in value.get('templates')
                if template.required is True
            ]
            if prev_req_templates != incoming_req_templates:
                raise serializers.ValidationError(
                    {'templates': 'Required templates cannot be Unassigned.'}
                )
            return value
        else:
            return value
