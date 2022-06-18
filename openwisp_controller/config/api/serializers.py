from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from swapper import load_model

from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer

Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
Device = load_model('config', 'Device')
DeviceGroup = load_model('config', 'DeviceGroup')
Config = load_model('config', 'Config')
Organization = load_model('openwisp_users', 'Organization')


class BaseMeta:
    read_only_fields = ['created', 'modified']


class BaseSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    pass


class TemplateSerializer(BaseSerializer):
    config = serializers.JSONField(initial={}, required=False)
    tags = serializers.StringRelatedField(many=True, read_only=True)
    default_values = serializers.JSONField(required=False, initial={})
    include_shared = True

    class Meta(BaseMeta):
        model = Template
        fields = [
            'id',
            'name',
            'organization',
            'type',
            'backend',
            'vpn',
            'tags',
            'default',
            'required',
            'default_values',
            'config',
            'created',
            'modified',
        ]

    def validate_vpn(self, value):
        """
        Ensure that VPN can't be added when
        template `Type` is set to `Generic`.
        """
        if self.initial_data.get('type') == 'generic' and value is not None:
            raise serializers.ValidationError(
                _("To select a VPN, set the template type to 'VPN-client'")
            )
        return value

    def validate_config(self, value):
        """
        Display appropriate field name.
        """
        if self.initial_data.get('type') == 'generic' and value == {}:
            raise serializers.ValidationError(
                _('The configuration field cannot be empty.')
            )
        return value


class VpnSerializer(BaseSerializer):
    config = serializers.JSONField(initial={})
    include_shared = True

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
            'created',
            'modified',
        ]


class FilterTemplatesByOrganization(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        user = self.context['request'].user
        if user.is_superuser:
            queryset = Template.objects.all()
        else:
            queryset = Template.objects.filter(
                Q(organization__in=user.organizations_managed)
                | Q(organization__isnull=True)
            )
        return queryset


class BaseConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = Config
        fields = ['status', 'backend', 'templates', 'context', 'config']
        extra_kwargs = {'status': {'read_only': True}}


class DeviceListConfigSerializer(BaseConfigSerializer):
    config = serializers.JSONField(
        initial={}, help_text=_('Configuration in NetJSON format'), write_only=True
    )
    context = serializers.JSONField(
        initial={},
        help_text=_('Configuration variables in JSON format'),
        write_only=True,
    )
    templates = FilterTemplatesByOrganization(many=True, write_only=True)


class DeviceListSerializer(FilterSerializerByOrgManaged, serializers.ModelSerializer):
    config = DeviceListConfigSerializer(required=False)

    class Meta(BaseMeta):
        model = Device
        fields = [
            'id',
            'name',
            'organization',
            'group',
            'mac_address',
            'key',
            'last_ip',
            'management_ip',
            'model',
            'os',
            'system',
            'notes',
            'config',
            'created',
            'modified',
        ]
        extra_kwargs = {
            'last_ip': {'allow_blank': True},
            'management_ip': {'allow_blank': True},
        }

    def create(self, validated_data):
        config_data = None
        if validated_data.get('config'):
            config_data = validated_data.pop('config')
            config_templates = [
                template.pk for template in config_data.pop('templates')
            ]

        with transaction.atomic():
            device = Device.objects.create(**validated_data)
            if config_data:
                config = Config.objects.create(device=device, **config_data)
                config.templates.add(*config_templates)
        return device


class DeviceDetailConfigSerializer(BaseConfigSerializer):
    config = serializers.JSONField(
        initial={}, help_text=_('Configuration in NetJSON format')
    )
    context = serializers.JSONField(
        initial={}, help_text=_('Configuration variables in JSON format')
    )
    templates = FilterTemplatesByOrganization(many=True)


class DeviceDetailSerializer(BaseSerializer):
    config = DeviceDetailConfigSerializer(allow_null=True)

    class Meta(BaseMeta):
        model = Device
        fields = [
            'id',
            'name',
            'organization',
            'group',
            'mac_address',
            'key',
            'last_ip',
            'management_ip',
            'model',
            'os',
            'system',
            'notes',
            'config',
            'created',
            'modified',
        ]

    def update(self, instance, validated_data):
        config_data = validated_data.pop('config', {})
        config_templates = [
            template.pk for template in config_data.get('templates', [])
        ]
        raw_data_for_signal_handlers = {
            'organization': validated_data.get('organization', instance.organization)
        }
        if self.initial_data.get('config.backend') and instance._has_config() is False:
            config_data = dict(config_data)
            with transaction.atomic():
                config = Config(device=instance, **config_data)
                config.templates.add(*config_templates)
                config.full_clean()
                config.save()
            return super().update(instance, validated_data)

        if config_data:
            instance.config.backend = config_data.get(
                'backend', instance.config.backend
            )
            instance.config.context = config_data.get(
                'context', instance.config.context
            )
            instance.config.config = config_data.get('config', instance.config.config)

            if 'templates' in config_data:
                if config_data.get('templates'):
                    new_config_templates = config_templates
                    old_config_templates = [
                        template
                        for template in instance.config.templates.values_list(
                            'pk', flat=True
                        )
                    ]
                    if new_config_templates != old_config_templates:
                        with transaction.atomic():
                            vpn_list = instance.config.templates.filter(
                                type='vpn'
                            ).values_list('vpn')
                            if vpn_list:
                                instance.config.vpnclient_set.exclude(
                                    vpn__in=vpn_list
                                ).delete()
                            instance.config.templates.clear()
                            instance.config.templates.add(*new_config_templates)
                else:
                    vpn_list = instance.config.templates.filter(type='vpn').values_list(
                        'vpn'
                    )
                    if vpn_list:
                        instance.config.vpnclient_set.exclude(vpn__in=vpn_list).delete()
                    instance.config.templates.clear()
                    instance.config.templates.add(*[])
            instance.config.save()

        elif hasattr(instance, 'config') and validated_data.get('organization'):
            if instance.organization != validated_data.get('organization'):
                # config.device.organization is used for validating
                # the organization of templates. It is also used for adding
                # default and required templates configured for an organization.
                # The value of the organization field is set here to
                # prevent access of the old value stored in the database
                # while performing above operations.
                instance.config.device.organization = validated_data.get('organization')
                instance.config.templates.clear()
                Config.enforce_required_templates(
                    action='post_clear',
                    instance=instance.config,
                    sender=instance.config.templates,
                    pk_set=None,
                    raw_data=raw_data_for_signal_handlers,
                )
        return super().update(instance, validated_data)


class DeviceGroupSerializer(BaseSerializer):
    meta_data = serializers.JSONField(required=False, initial={})

    class Meta(BaseMeta):
        model = DeviceGroup
        fields = [
            'id',
            'name',
            'organization',
            'description',
            'meta_data',
            'created',
            'modified',
        ]
