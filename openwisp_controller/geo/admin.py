import reversion
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django_loci.base.admin import (
    AbstractFloorPlanAdmin,
    AbstractFloorPlanForm,
    AbstractFloorPlanInline,
    AbstractLocationAdmin,
    AbstractLocationForm,
    AbstractObjectLocationForm,
    ObjectLocationMixin,
)
from swapper import load_model

from openwisp_users.multitenancy import MultitenantOrgFilter

from ..admin import MultitenantAdminMixin
from ..config.admin import DeactivatedDeviceReadOnlyMixin, DeviceAdminExportable
from .exportable import GeoDeviceResource

DeviceLocation = load_model('geo', 'DeviceLocation')
FloorPlan = load_model('geo', 'FloorPlan')
Location = load_model('geo', 'Location')


class FloorPlanForm(AbstractFloorPlanForm):
    class Meta(AbstractFloorPlanForm.Meta):
        model = FloorPlan
        exclude = ('organization',)  # automatically managed


class FloorPlanInline(AbstractFloorPlanInline):
    form = FloorPlanForm
    model = FloorPlan


class FloorPlanAdmin(MultitenantAdminMixin, AbstractFloorPlanAdmin):
    form = FloorPlanForm
    list_filter = [MultitenantOrgFilter, 'created']


FloorPlanAdmin.list_display.insert(1, 'organization')


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

    def _get_initial_location(self):
        """
        Returns initial location for the device.

        Attempts to get the initial location by calling parent class method.
        If location is not found (e.g. when recovering a deleted device),
        returns None instead of raising Location.DoesNotExist.

        Returns:
            Location instance or None if location does not exist
        """
        try:
            return super()._get_initial_location()
        except Location.DoesNotExist:
            return None

    def _get_initial_floorplan(self):
        """
        Returns initial floorplan for the device.

        Attempts to get the initial floorplan by calling parent class method.
        If floorplan is not found (e.g. when recovering a deleted device),
        returns None instead of raising FloorPlan.DoesNotExist.

        Returns:
            FloorPlan instance or None if floorplan does not exist
        """
        try:
            return super()._get_initial_floorplan()
        except FloorPlan.DoesNotExist:
            return None


class LocationForm(AbstractLocationForm):
    class Meta(AbstractLocationForm.Meta):
        model = Location


class LocationAdmin(MultitenantAdminMixin, AbstractLocationAdmin):
    form = LocationForm
    inlines = [FloorPlanInline]
    list_select_related = ('organization',)


LocationAdmin.list_display.insert(1, 'organization')
LocationAdmin.list_filter.insert(0, MultitenantOrgFilter)


class DeviceLocationInline(
    ObjectLocationMixin, DeactivatedDeviceReadOnlyMixin, admin.StackedInline
):
    model = DeviceLocation
    form = ObjectLocationForm
    verbose_name = _('Map')
    verbose_name_plural = verbose_name


admin.site.register(FloorPlan, FloorPlanAdmin)
admin.site.register(Location, LocationAdmin)
reversion.register(model=Location)


class DeviceLocationFilter(admin.SimpleListFilter):
    title = _('has geographic position set?')
    parameter_name = 'with_geo'

    def lookups(self, request, model_admin):
        return (
            ('true', _('Yes')),
            ('false', _('No')),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(devicelocation__isnull=self.value() == 'false')
        return queryset


# Prepend DeviceLocationInline to config.DeviceAdminExportable
DeviceAdminExportable.inlines.insert(1, DeviceLocationInline)
DeviceAdminExportable.list_filter.append(DeviceLocationFilter)
DeviceAdminExportable.resource_class = GeoDeviceResource
reversion.register(model=DeviceLocation, follow=['device', 'location'])
DeviceAdminExportable.add_reversion_following(follow=['devicelocation'])
