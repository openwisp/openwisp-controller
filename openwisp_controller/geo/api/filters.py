from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters

from openwisp_controller.config import settings as config_app_settings
from openwisp_controller.config.api.filters import (
    DeviceListFilter as BaseDeviceListFilter,
)


class DeviceListFilter(BaseDeviceListFilter):
    # Using filter query param name `with_geo`
    # which is similar to admin filter
    with_geo = filters.BooleanFilter(
        field_name="devicelocation",
        method="filter_devicelocation",
        label=_("Has geographic location set?"),
    )
    location__name = filters.CharFilter(
        field_name="devicelocation__location__name",
        lookup_expr="icontains",
        label=_("Location name"),
    )
    location = filters.UUIDFilter(
        field_name="devicelocation__location", label=_("Location UUID")
    )
    floorplan = filters.UUIDFilter(
        field_name="devicelocation__floorplan", label=_("Floor plan UUID")
    )

    def filter_devicelocation(self, queryset, name, value):
        # Returns list of device that have devicelocation objects
        return queryset.exclude(devicelocation__isnull=value)

    def filter_is_estimated(self, queryset, name, value):
        return queryset.filter(devicelocation__location__is_estimated=value)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if config_app_settings.WHOIS_CONFIGURED:
            self.filters["geo_is_estimated"] = filters.BooleanFilter(
                field_name="devicelocation__location__is_estimated",
                method=self.filter_is_estimated,
            )
            self.filters["geo_is_estimated"].label = _(
                "Is geographic location estimated?"
            )

    class Meta:
        model = BaseDeviceListFilter.Meta.model
        geo_fields = [
            "with_geo",
            "location__name",
            "location",
            "floorplan",
        ]
        fields = BaseDeviceListFilter.Meta.fields
        index_created = fields.index("created")
        fields[index_created:index_created] = geo_fields
