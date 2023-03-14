from django_filters import rest_framework as filters
from swapper import load_model

Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
Device = load_model('config', 'Device')
DeviceGroup = load_model('config', 'DeviceGroup')


class BaseConfigAPIFilter(filters.FilterSet):
    organization = filters.CharFilter(field_name='organization', label='Organization')

    def _set_valid_filterform_lables(self):
        # When not filtering on a model field, an error message
        # with the label "[invalid_name]" will be displayed in filter form.
        # To avoid this error, you need to provide the label explicitly.
        raise NotImplementedError


class TemplateListFilter(BaseConfigAPIFilter):
    class Meta:
        model = Template
        fields = {
            'organization': ['exact'],
            'backend': ['exact'],
            'type': ['exact'],
            'default': ['exact'],
            'required': ['exact'],
            'created': ['exact', 'gte', 'lt'],
        }


class VPNListFilter(BaseConfigAPIFilter):

    subnet = filters.CharFilter(field_name='subnet', label='VPN Subnet')

    class Meta:
        model = Vpn
        fields = {
            'backend': ['exact'],
            'subnet': ['exact'],
            'organization': ['exact'],
        }


class DeviceListFilter(BaseConfigAPIFilter):
    config__templates = filters.CharFilter(
        field_name='config__templates', label='Config template'
    )
    group = filters.CharFilter(field_name='group', label='Device group')
    devicelocation = filters.BooleanFilter(
        field_name='devicelocation', method='filter_devicelocation'
    )

    def filter_devicelocation(self, queryset, name, value):
        # Returns list of device that have devicelocation objects
        return queryset.exclude(devicelocation__isnull=value)

    def _set_valid_filterform_lables(self):
        self.filters['config__status'].label = 'Config status'
        self.filters['config__backend'].label = 'Config backend'
        self.filters['devicelocation'].label = 'DeviceLocation'

    def __init__(self, *args, **kwargs):
        super(DeviceListFilter, self).__init__(*args, **kwargs)
        self._set_valid_filterform_lables()

    class Meta:
        model = Device
        fields = {
            'config__status': ['exact'],
            'config__backend': ['exact'],
            'organization': ['exact'],
            'config__templates': ['exact'],
            'group': ['exact'],
            'devicelocation': ['exact'],
            'created': ['exact', 'gte', 'lt'],
        }


class DeviceGroupListFilter(BaseConfigAPIFilter):
    device = filters.BooleanFilter(field_name='device', method='filter_device')

    def filter_device(self, queryset, name, value):
        # Returns list of device groups that have devicelocation objects
        return queryset.exclude(device__isnull=value).distinct()

    def _set_valid_filterform_lables(self):
        self.filters['device'].label = 'Has devices'

    def __init__(self, *args, **kwargs):
        super(DeviceGroupListFilter, self).__init__(*args, **kwargs)
        self._set_valid_filterform_lables()

    class Meta:
        model = DeviceGroup
        fields = {
            'organization': ['exact'],
            'device': ['exact'],
        }
