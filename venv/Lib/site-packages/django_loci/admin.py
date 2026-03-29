from django.contrib import admin

from .base.admin import (
    AbstractFloorPlanAdmin,
    AbstractFloorPlanForm,
    AbstractFloorPlanInline,
    AbstractLocationAdmin,
    AbstractLocationForm,
    AbstractObjectLocationForm,
    AbstractObjectLocationInline,
)
from .models import FloorPlan, Location, ObjectLocation


class FloorPlanForm(AbstractFloorPlanForm):
    class Meta(AbstractFloorPlanForm.Meta):
        model = FloorPlan


class FloorPlanAdmin(AbstractFloorPlanAdmin):
    form = FloorPlanForm


class LocationForm(AbstractLocationForm):
    class Meta(AbstractLocationForm.Meta):
        model = Location


class FloorPlanInline(AbstractFloorPlanInline):
    form = FloorPlanForm
    model = FloorPlan


class LocationAdmin(AbstractLocationAdmin):
    form = LocationForm
    inlines = [FloorPlanInline]


class ObjectLocationForm(AbstractObjectLocationForm):
    class Meta(AbstractObjectLocationForm.Meta):
        model = ObjectLocation


class ObjectLocationInline(AbstractObjectLocationInline):
    model = ObjectLocation
    form = ObjectLocationForm


admin.site.register(FloorPlan, FloorPlanAdmin)
admin.site.register(Location, LocationAdmin)
