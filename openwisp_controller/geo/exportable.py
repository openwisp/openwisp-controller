from django.core.exceptions import ObjectDoesNotExist
from import_export.fields import Field

from ..config.exportable import DeviceResource


class GeoDeviceResource(DeviceResource):
    venue = Field(attribute='devicelocation__location__name', column_name='venue')
    address = Field(
        attribute='devicelocation__location__address', column_name='address'
    )
    coords = Field(attribute='devicelocation__location__geometry', column_name='coords')
    is_mobile = Field(
        attribute='devicelocation__location__is_mobile', column_name='is_mobile'
    )
    venue_type = Field(
        attribute='devicelocation__location__type', column_name='venue_type'
    )
    floor = Field(attribute='devicelocation__floorplan__floor', column_name='floor')
    floor_position = Field(
        attribute='devicelocation__indoor', column_name='floor_position'
    )
    location_id = Field(
        attribute='devicelocation__location_id', column_name='location_id'
    )
    floorplan_id = Field(
        attribute='devicelocation__floorplan_id', column_name='floorplan_id'
    )

    def dehydrate_coords(self, device):
        try:
            return device.devicelocation.location.geometry.wkt
        except ObjectDoesNotExist:
            pass

    class Meta(DeviceResource.Meta):
        fields = DeviceResource.Meta.fields[:]  # copy
        # add geo fields after before last_ip
        # fmt: off
        fields[fields.index('last_ip'):fields.index('last_ip')] = [
            'venue',
            'address',
            'coords',
            'is_mobile',
            'venue_type',
            'floor',
            'floor_position',
        ]
        # fmt: on
        # add id fields at the end
        fields += ['location_id', 'floorplan_id']
        export_order = fields
