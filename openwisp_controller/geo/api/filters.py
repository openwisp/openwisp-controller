from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters

from openwisp_controller.config.api.filters import (
    DeviceListFilter as BaseDeviceListFilter,
)


class DeviceListFilter(BaseDeviceListFilter):
    # Using filter query param name `with_geo`
    # which is similar to admin filter
    with_geo = filters.BooleanFilter(
        field_name='devicelocation', method='filter_devicelocation'
    )

    def _set_valid_filterform_lables(self):
        super()._set_valid_filterform_lables()
        self.filters['with_geo'].label = _('Has geographic location set?')

    def filter_devicelocation(self, queryset, name, value):
        # Returns list of device that have devicelocation objects
        return queryset.exclude(devicelocation__isnull=value)

    class Meta:
        model = BaseDeviceListFilter.Meta.model
        fields = BaseDeviceListFilter.Meta.fields[:]
        fields.insert(fields.index('created'), 'with_geo')
