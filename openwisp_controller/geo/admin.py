from django.contrib import admin
from django_loci.base.admin import (AbstractFloorPlanAdmin, AbstractFloorPlanForm, AbstractFloorPlanInline,
                                    AbstractLocationAdmin, AbstractLocationForm, AbstractObjectLocationForm,
                                    ObjectLocationMixin)

from openwisp_utils.admin import MultitenantOrgFilter

from ..admin import MultitenantAdminMixin
from ..config.admin import ConfigInline
from ..config.admin import DeviceAdmin as BaseDeviceAdmin
from ..config.models import Device
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
        location = super(ObjectLocationForm, self)._get_location_instance()
        location.organization_id = self.data.get('organization')
        return location

    def _get_floorplan_instance(self):
        floorplan = super(ObjectLocationForm, self)._get_floorplan_instance()
        floorplan.organization_id = self.data.get('organization')
        return floorplan


class DeviceLocationInline(ObjectLocationMixin, admin.StackedInline):
    model = DeviceLocation
    form = ObjectLocationForm


admin.site.register(FloorPlan, FloorPlanAdmin)
admin.site.register(Location, LocationAdmin)


# Add DeviceLocationInline to config.DeviceAdmin

class GeoDeviceAdmin(BaseDeviceAdmin):
    inlines = [DeviceLocationInline, ConfigInline]


admin.site.unregister(Device)
admin.site.register(Device, GeoDeviceAdmin)
