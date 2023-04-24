from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters
from swapper import load_model

Device = load_model('config', 'Device')


class DeviceLocationFilter(filters.FilterSet):
    # Using filter query param name `with_geo`
    # which is similar to admin filter
    with_geo = filters.BooleanFilter(
        field_name='devicelocation', method='filter_devicelocation'
    )

    def _set_valid_filterform_lables(self):
        self.filters['with_geo'].label = _('Has geographic location set?')

    def __init__(self, *args, **kwargs):
        super(DeviceLocationFilter, self).__init__(*args, **kwargs)
        self._set_valid_filterform_lables()

    class Meta:
        model = Device
        fields = ['with_geo']
