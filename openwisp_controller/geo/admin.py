from django.contrib import admin
from django_loci.base.admin import (AbstractFloorPlanAdmin, AbstractFloorPlanForm, AbstractFloorPlanInline,
                                    AbstractLocationAdmin, AbstractLocationForm, AbstractObjectLocationForm,
                                    ObjectLocationMixin)

from openwisp_users.multitenancy import MultitenantOrgFilter

from ..admin import MultitenantAdminMixin
from ..config.admin import DeviceAdmin
from .models import DeviceLocation, FloorPlan, Location


class FloorPlanForm(AbstractFloorPlanForm):
    class Meta(AbstractFloorPlanForm.Meta):
        model = FloorPlan
        exclude = ('organization',)  # automatically managed


class FloorPlanAdmin(MultitenantAdminMixin, AbstractFloorPlanAdmin):
    form = FloorPlanForm
    list_filter = [('organization', MultitenantOrgFilter),
                   'created']


FloorPlanAdmin.list_display.insert(1, 'organization')


class LocationForm(AbstractLocationForm):
    class Meta(AbstractLocationForm.Meta):
        model = Location


class FloorPlanInline(AbstractFloorPlanInline):
    form = FloorPlanForm
    model = FloorPlan


class LocationAdmin(MultitenantAdminMixin, AbstractLocationAdmin):
    form = LocationForm
    inlines = [FloorPlanInline]
    list_select_related = ('organization',)


LocationAdmin.list_display.insert(1, 'organization')
LocationAdmin.list_filter.insert(0, ('organization', MultitenantOrgFilter))


class ObjectLocationForm(AbstractObjectLocationForm):
    class Meta(AbstractObjectLocationForm.Meta):
        model = DeviceLocation

    def _get_location_instance(self):
        location = super()._get_location_instance()
        location.organization_id = self.data.get('organization')
        return location

    def _get_floorplan_instance(self):
        floorplan = super()._get_floorplan_instance()
        floorplan.organization_id = self.data.get('organization')
        return floorplan


class DeviceLocationInline(ObjectLocationMixin, admin.StackedInline):
    model = DeviceLocation
    form = ObjectLocationForm


admin.site.register(FloorPlan, FloorPlanAdmin)
admin.site.register(Location, LocationAdmin)


# Prepend DeviceLocationInline to config.DeviceAdmin
DeviceAdmin.inlines.insert(0, DeviceLocationInline)
