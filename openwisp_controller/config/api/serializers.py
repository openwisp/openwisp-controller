from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from swapper import load_model

from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer

from .. import settings as app_settings

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
        fields = ['status', 'error_reason', 'backend', 'templates', 'context', 'config']
        extra_kwargs = {
            'status': {'read_only': True},
            'error_reason': {'read_only': True},
        }


class DeviceConfigMixin(object):
    def _get_config_templates(self, config_data):
        return [template.pk for template in config_data.pop('templates', [])]

    def _prepare_config(self, device, config_data):
        config = device.config
        for key, value in config_data.items():
            setattr(config, key, value)
        config.full_clean()
        return config

    @transaction.atomic
    def _create_config(self, device, config_data):
        config_templates = self._get_config_templates(config_data)
        try:
            if not device._has_config():
                config = Config(device=device, **config_data)
                config.full_clean()
                config.save()
            else:
                # If the "device group" was specified, then
                # the config would get automatically created
                # for the device. Hence, we perform update
                # operation on config of a new device.
                config = self._prepare_config(device, config_data)
                config.save()
            config.templates.add(*config_templates)
        except ValidationError as error:
            raise serializers.ValidationError({'config': error.messages})

    def _update_config(self, device, config_data):
        if (
            config_data.get('backend') == app_settings.DEFAULT_BACKEND
            and not config_data.get('templates')
            and not config_data.get('context')
            and not config_data.get('config')
        ):
            # Do not create Config object if config_data only
            # contains the default value.
            # See https://github.com/openwisp/openwisp-controller/issues/699
            return
        if not device._has_config():
            return self._create_config(device, config_data)
        config_templates = self._get_config_templates(config_data)
        try:
            config = self._prepare_config(device, config_data)
            old_templates = list(config.templates.values_list('id', flat=True))
            if config_templates != old_templates:
                with transaction.atomic():
                    vpn_list = config.templates.filter(type='vpn').values_list('vpn')
                    if vpn_list:
                        config.vpnclient_set.exclude(vpn__in=vpn_list).delete()
                    config.templates.set(config_templates, clear=True)
            config.save()
        except ValidationError as error:
            raise serializers.ValidationError({'config': error.messages})


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


class DeviceListSerializer(
    DeviceConfigMixin, FilterSerializerByOrgManaged, serializers.ModelSerializer
):
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

    def validate(self, attrs):
        device_data = deepcopy(attrs)
        # Validation of "config" is performed after
        # device object is created in the "create" method.
        device_data.pop('config', None)
        device = self.instance or self.Meta.model(**device_data)
        device.full_clean()
        return attrs

    def create(self, validated_data):
        config_data = validated_data.pop('config', None)
        with transaction.atomic():
            device = Device.objects.create(**validated_data)
            if config_data:
                self._create_config(device, config_data)
        return device


class DeviceDetailConfigSerializer(BaseConfigSerializer):
    config = serializers.JSONField(
        initial={}, help_text=_('Configuration in NetJSON format')
    )
    context = serializers.JSONField(
        initial={}, help_text=_('Configuration variables in JSON format')
    )
    templates = FilterTemplatesByOrganization(many=True)


class DeviceDetailSerializer(DeviceConfigMixin, BaseSerializer):
    config = DeviceDetailConfigSerializer(allow_null=True)
    is_deactivated = serializers.BooleanField(read_only=True)

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
            'is_deactivated',
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
        raw_data_for_signal_handlers = {
            'organization': validated_data.get('organization', instance.organization)
        }
        if config_data:
            self._update_config(instance, config_data)

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


class FilterGroupTemplates(FilterTemplatesByOrganization):
    def get_queryset(self):
        return super().get_queryset().exclude(Q(default=True) | Q(required=True))


class DeviceGroupSerializer(BaseSerializer):
    context = serializers.JSONField(required=False, initial={})
    meta_data = serializers.JSONField(required=False, initial={})
    templates = FilterGroupTemplates(many=True)
    _templates = None

    class Meta(BaseMeta):
        model = DeviceGroup
        fields = [
            'id',
            'name',
            'organization',
            'description',
            'templates',
            'context',
            'meta_data',
            'created',
            'modified',
        ]

    def validate(self, data):
        self._templates = [template.id for template in data.pop('templates', [])]
        return super().validate(data)

    def _save_m2m_templates(self, instance, created=False):
        old_templates = list(instance.templates.values_list('pk', flat=True))
        if old_templates != self._templates:
            instance.templates.set(self._templates)
            if not created:
                self.Meta.model.templates_changed(
                    instance=instance,
                    old_templates=old_templates,
                    templates=self._templates,
                )

    def create(self, validated_data):
        instance = super().create(validated_data)
        self._save_m2m_templates(instance, created=True)
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        self._save_m2m_templates(instance)
        return instance
