import swapper

from .base.models import (
    AbstractOrganizationGeoSettings,
    BaseDeviceLocation,
    BaseFloorPlan,
    BaseLocation,
)


class Location(BaseLocation):
    class Meta(BaseLocation.Meta):
        abstract = False
        swappable = swapper.swappable_setting("geo", "Location")


class FloorPlan(BaseFloorPlan):
    class Meta(BaseFloorPlan.Meta):
        abstract = False
        swappable = swapper.swappable_setting("geo", "FloorPlan")


class DeviceLocation(BaseDeviceLocation):
    class Meta(BaseDeviceLocation.Meta):
        abstract = False
        swappable = swapper.swappable_setting("geo", "DeviceLocation")


class OrganizationGeoSettings(AbstractOrganizationGeoSettings):
    class Meta(AbstractOrganizationGeoSettings.Meta):
        abstract = False
        swappable = swapper.swappable_setting("geo", "OrganizationGeoSettings")


# maintain compatibility with django_loci
Location.objectlocation_set = Location.devicelocation_set
FloorPlan.objectlocation_set = FloorPlan.devicelocation_set
