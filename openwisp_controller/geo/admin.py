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
from ..config.admin import DeviceAdmin

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
    list_filter = [('organization', MultitenantOrgFilter), 'created']


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


class LocationForm(AbstractLocationForm):
    class Meta(AbstractLocationForm.Meta):
        model = Location


class LocationAdmin(MultitenantAdminMixin, AbstractLocationAdmin):
    form = LocationForm
    inlines = [FloorPlanInline]
    list_select_related = ('organization',)


LocationAdmin.list_display.insert(1, 'organization')
LocationAdmin.list_filter.insert(0, ('organization', MultitenantOrgFilter))


class DeviceLocationInline(ObjectLocationMixin, admin.StackedInline):
    model = DeviceLocation
    form = ObjectLocationForm
    verbose_name = _('Map')
    verbose_name_plural = verbose_name


admin.site.register(FloorPlan, FloorPlanAdmin)
admin.site.register(Location, LocationAdmin)


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


# Prepend DeviceLocationInline to config.DeviceAdmin
DeviceAdmin.inlines.insert(1, DeviceLocationInline)
DeviceAdmin.list_filter.append(DeviceLocationFilter)
reversion.register(model=DeviceLocation, follow=['device'])
DeviceAdmin.add_reversion_following(follow=['devicelocation'])
