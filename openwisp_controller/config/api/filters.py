from uuid import UUID

from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import ValidationError
from swapper import load_model

from openwisp_controller.geo.api.views import BaseOrganizationFilter

Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
Device = load_model('config', 'Device')
DeviceGroup = load_model('config', 'DeviceGroup')


class BaseConfigAPIFilter(BaseOrganizationFilter):
    def _set_valid_filterform_lables(self):
        # When not filtering on a model field, an error message
        # with the label "[invalid_name]" will be displayed in filter form.
        # To avoid this error, we need to provide the label explicitly.
        raise NotImplementedError


class TemplateListFilter(BaseConfigAPIFilter):
    class Meta:
        model = Template
        fields = {
            'backend': ['exact'],
            'type': ['exact'],
            'default': ['exact'],
            'required': ['exact'],
            'created': ['exact', 'gte', 'lt'],
        }


class VPNListFilter(BaseConfigAPIFilter):

    subnet = filters.CharFilter(field_name='subnet', label=_('VPN Subnet'))

    class Meta:
        model = Vpn
        fields = {
            'backend': ['exact'],
            'subnet': ['exact'],
        }


class DeviceListFilterBackend(DjangoFilterBackend):
    def filter_queryset(self, request, queryset, view):
        """
        Validate that the request parameters contain
        a valid configuration template uuid format
        """
        config_template_uuid = request.query_params.get('config__templates')
        if config_template_uuid:
            try:
                # Attempt to convert the uuid string to a UUID object
                config_template_uuid_obj = UUID(config_template_uuid)
            except ValueError:
                raise ValidationError({'config__templates': 'Invalid UUID format'})
            # Add the config__templates filter to the queryset
            return queryset.filter(config__templates=config_template_uuid_obj)
        return super().filter_queryset(request, queryset, view)


class DeviceListFilter(BaseConfigAPIFilter):
    config__templates = filters.CharFilter(
        field_name='config__templates', label=_('Config template')
    )
    group = filters.CharFilter(field_name='group', label=_('Device group'))
    # Using filter query param name `with_geo`
    # which is similar to admin filter
    with_geo = filters.BooleanFilter(
        field_name='devicelocation', method='filter_devicelocation'
    )

    def filter_devicelocation(self, queryset, name, value):
        # Returns list of device that have devicelocation objects
        return queryset.exclude(devicelocation__isnull=value)

    def _set_valid_filterform_lables(self):
        self.filters['config__status'].label = _('Config status')
        self.filters['config__backend'].label = _('Config backend')
        self.filters['with_geo'].label = _('Has geographic location set?')

    def __init__(self, *args, **kwargs):
        super(DeviceListFilter, self).__init__(*args, **kwargs)
        self._set_valid_filterform_lables()

    class Meta:
        model = Device
        fields = {
            'config__status': ['exact'],
            'config__backend': ['exact'],
            'config__templates': ['exact'],
            'group': ['exact'],
            'created': ['exact', 'gte', 'lt'],
        }


class DeviceGroupListFilter(BaseConfigAPIFilter):
    # Using filter query param name `empty`
    # which is similar to admin filter
    empty = filters.BooleanFilter(field_name='device', method='filter_device')

    def filter_device(self, queryset, name, value):
        # Returns list of device groups that have devicelocation objects
        return queryset.exclude(device__isnull=value).distinct()

    def _set_valid_filterform_lables(self):
        self.filters['empty'].label = _('Has devices?')

    def __init__(self, *args, **kwargs):
        super(DeviceGroupListFilter, self).__init__(*args, **kwargs)
        self._set_valid_filterform_lables()

    class Meta(BaseConfigAPIFilter.Meta):
        model = DeviceGroup
