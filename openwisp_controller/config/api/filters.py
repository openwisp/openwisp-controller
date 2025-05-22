from uuid import UUID

from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import ValidationError
from swapper import load_model

from openwisp_users.api.filters import OrganizationManagedFilter

Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
Device = load_model('config', 'Device')
DeviceGroup = load_model('config', 'DeviceGroup')


class BaseConfigAPIFilter(OrganizationManagedFilter):
    def _set_valid_filterform_lables(self):
        # When not filtering on a model field, an error message
        # with the label "[invalid_name]" will be displayed in filter form.
        # To avoid this error, we need to provide the label explicitly.
        raise NotImplementedError


class TemplateListFilter(BaseConfigAPIFilter):
    created__gte = filters.DateTimeFilter(
        field_name='created',
        lookup_expr='gte',
    )
    created__lt = filters.DateTimeFilter(
        field_name='created',
        lookup_expr='lt',
    )

    def _set_valid_filterform_lables(self):
        self.filters['backend'].label = _('Template backend')
        self.filters['type'].label = _('Template type')

    def __init__(self, *args, **kwargs):
        super(TemplateListFilter, self).__init__(*args, **kwargs)
        self._set_valid_filterform_lables()

    class Meta(BaseConfigAPIFilter.Meta):
        model = Template
        fields = BaseConfigAPIFilter.Meta.fields + [
            'backend',
            'type',
            'default',
            'required',
            'created',
        ]


class VPNListFilter(BaseConfigAPIFilter):
    def _set_valid_filterform_lables(self):
        self.filters['backend'].label = _('VPN Backend')
        self.filters['subnet'].label = _('VPN Subnet')

    def __init__(self, *args, **kwargs):
        super(VPNListFilter, self).__init__(*args, **kwargs)
        self._set_valid_filterform_lables()

    class Meta(BaseConfigAPIFilter.Meta):
        model = Vpn
        fields = BaseConfigAPIFilter.Meta.fields + ['backend', 'subnet']


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
                raise ValidationError({'config__templates': _('Invalid UUID format')})
            # Add the config__templates filter to the queryset
            return queryset.filter(config__templates=config_template_uuid_obj)
        return super().filter_queryset(request, queryset, view)


class DeviceListFilter(BaseConfigAPIFilter):
    mac_address = filters.CharFilter(
        field_name='mac_address',
        lookup_expr='icontains',
    )
    name = filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
    )
    created__gte = filters.DateTimeFilter(
        field_name='created',
        lookup_expr='gte',
    )
    created__lt = filters.DateTimeFilter(
        field_name='created',
        lookup_expr='lt',
    )

    def _set_valid_filterform_lables(self):
        self.filters['group'].label = _('Device group')
        self.filters['config__templates'].label = _('Config template')
        self.filters['config__status'].label = _('Config status')
        self.filters['config__backend'].label = _('Config backend')

    def __init__(self, *args, **kwargs):
        super(DeviceListFilter, self).__init__(*args, **kwargs)
        self._set_valid_filterform_lables()

    class Meta(BaseConfigAPIFilter.Meta):
        model = Device
        fields = BaseConfigAPIFilter.Meta.fields + [
            'name',
            'mac_address',
            'config__status',
            'config__backend',
            'config__templates',
            'group',
            'created',
        ]


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
