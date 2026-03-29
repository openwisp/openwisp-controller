from .base.models import AbstractFloorPlan, AbstractLocation, AbstractObjectLocation


class Location(AbstractLocation):
    class Meta(AbstractLocation.Meta):
        abstract = False


class FloorPlan(AbstractFloorPlan):
    class Meta(AbstractFloorPlan.Meta):
        abstract = False


class ObjectLocation(AbstractObjectLocation):
    class Meta(AbstractObjectLocation.Meta):
        abstract = False
