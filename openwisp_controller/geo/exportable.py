from django.core.exceptions import ObjectDoesNotExist
from import_export.fields import Field
from swapper import load_model

from ..config.exportable import DeviceResource

DeviceLocation = load_model('geo', 'DeviceLocation')


class GeoDeviceResource(DeviceResource):
    venue = Field(
        attribute='devicelocation__location__name', column_name='venue', readonly=True
    )
    address = Field(
        attribute='devicelocation__location__address',
        column_name='address',
        readonly=True,
    )
    coords = Field(
        attribute='devicelocation__location__geometry',
        column_name='coords',
        readonly=True,
    )
    is_mobile = Field(
        attribute='devicelocation__location__is_mobile',
        column_name='is_mobile',
        readonly=True,
    )
    venue_type = Field(
        attribute='devicelocation__location__type',
        column_name='venue_type',
        readonly=True,
    )
    floor = Field(
        attribute='devicelocation__floorplan__floor', column_name='floor', readonly=True
    )
    floor_position = Field(
        attribute='devicelocation__indoor', column_name='floor_position', default=None
    )
    location_id = Field(
        attribute='devicelocation__location_id', column_name='location_id', default=None
    )
    floorplan_id = Field(
        attribute='devicelocation__floorplan_id',
        column_name='floorplan_id',
        default=None,
    )

    def dehydrate_coords(self, device):
        try:
            return device.devicelocation.location.geometry.wkt
        except (ObjectDoesNotExist, AttributeError):
            pass

    def after_import_instance(self, instance, new, row_number=None, **kwargs):
        super().after_import_instance(instance, new, row_number, **kwargs)
        if not hasattr(instance, 'devicelocation'):
            instance.devicelocation = DeviceLocation()

    def validate_instance(
        self, instance, import_validation_errors=None, validate_unique=True
    ):
        super().validate_instance(
            instance, import_validation_errors=None, validate_unique=True
        )
        # make sure device id on devicelocation instance is set correctly
        device_location = instance.devicelocation
        if device_location.location_id or device_location.floorplan_id:
            device_location.content_object_id = instance.id

    def after_save_instance(self, instance, using_transactions, dry_run):
        super().after_save_instance(instance, using_transactions, dry_run)
        if not dry_run:
            device_location = instance.devicelocation
            if device_location.location_id or device_location.floorplan_id:
                device_location.save()

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
