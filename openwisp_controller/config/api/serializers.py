import ast
import collections
import json

from django.db import transaction
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers
from swapper import load_model

from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer

Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
Device = load_model('config', 'Device')
Config = load_model('config', 'Config')
Organization = load_model('openwisp_users', 'Organization')


class BaseMeta:
    read_only_fields = ['created', 'modified']


class BaseSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    pass


class TemplateSerializer(BaseSerializer):
    config = serializers.JSONField(initial={})
    tags = serializers.StringRelatedField(many=True, read_only=True)
    default_values = serializers.JSONField(required=False, initial={})

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


class VpnSerializer(BaseSerializer):
    config = serializers.JSONField(initial={})

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


class BaseJsonField(serializers.Field):
    def to_internal_value(self, data):
        if type(data) is str:
            if len(data) < 2:
                data = '{}'
            return ast.literal_eval(data)
        else:
            return data


class JsonConfigField(BaseJsonField):
    def to_representation(self, value):
        return json.loads(json.dumps(value))


class JsonContextField(BaseJsonField):
    def to_representation(self, value):
        return dict(value)


class FilterTemplatesByOrganization(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        user = self.context['request'].user
        if user.is_superuser:
            queryset = Template.objects.all()
        else:
            org_id = next(iter(user.organizations_dict))
            queryset = Template.objects.filter(
                Q(organization=None) | Q(organization=org_id)
            )
        return queryset


class DeviceConfigSerializer(serializers.ModelSerializer):
    config = JsonConfigField(
        help_text='''<i>config</i> field in HTML form
        displays values in dictionary format''',
        style={'base_template': 'textarea.html', 'placeholder': '{}'},
    )
    context = JsonContextField(
        help_text='''<i>context</i> field in HTML form
        displays values in dictionary format''',
        style={'base_template': 'textarea.html', 'placeholder': '{}'},
    )
    templates = FilterTemplatesByOrganization(many=True)

    class Meta:
        model = Config
        fields = ['backend', 'status', 'templates', 'context', 'config']
        extra_kwargs = {'status': {'read_only': True}}


class DeviceListSerializer(FilterSerializerByOrgManaged, serializers.ModelSerializer):
    config = DeviceConfigSerializer(write_only=True, required=False)
    status = serializers.SerializerMethodField()
    backend = serializers.SerializerMethodField()

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
            'status',
            'backend',
            'config',
        ]
        extra_kwargs = {
            'last_ip': {'allow_blank': True},
            'management_ip': {'allow_blank': True},
        }

    def get_status(self, obj):
        if obj._has_config():
            return obj.status

    def get_backend(self, obj):
        if obj._has_config():
            return obj.backend

    def create(self, validated_data):
        if validated_data.get('config'):
            config_data = validated_data.pop('config')
            with transaction.atomic():
                new_device = Device.objects.create(**validated_data)
                config_templates = [
                    template.pk for template in config_data.pop('templates')
                ]
                config = Config.objects.create(device=new_device, **config_data)
                config.templates.add(*config_templates)
            device = new_device
        else:
            with transaction.atomic():
                device = Device.objects.create(**validated_data)
        return device


class DeviceDetailSerializer(BaseSerializer):
    config = DeviceConfigSerializer(allow_null=True)

    class Meta(BaseMeta):
        model = Device
        fields = DeviceListSerializer.Meta.fields

    def update(self, instance, validated_data):
        config_data = None

        if self.initial_data.get('config.backend') and instance._has_config() is False:
            new_config_data = dict(validated_data.pop('config'))
            config_templates = [
                template.pk for template in new_config_data.pop('templates')
            ]
            with transaction.atomic():
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
                with transaction.atomic():
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

    def validate_config(self, value):
        """
            Raise Exception when removing
            templates flagged as required.
        """
        instance = self.instance
        if instance._has_config():
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
                    {'templates': _('Required templates cannot be Unassigned.')}
                )
        return value
