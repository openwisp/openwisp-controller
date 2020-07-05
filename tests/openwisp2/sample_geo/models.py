from django.db import models

from openwisp_controller.geo.base.models import (
    BaseDeviceLocation,
    BaseFloorPlan,
    BaseLocation,
)


class DetailsModel(models.Model):
    details = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        abstract = True


class Location(DetailsModel, BaseLocation):
    class Meta(BaseLocation.Meta):
        abstract = False


class FloorPlan(DetailsModel, BaseFloorPlan):
    class Meta(BaseFloorPlan.Meta):
        abstract = False


class DeviceLocation(DetailsModel, BaseDeviceLocation):
    class Meta(BaseDeviceLocation.Meta):
        abstract = False


# maintain compatibility with django_loci
Location.objectlocation_set = Location.devicelocation_set
FloorPlan.objectlocation_set = FloorPlan.devicelocation_set
