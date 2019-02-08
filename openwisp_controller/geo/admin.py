from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
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

    def clean_floorplan(self):
        floorplan_model = self.floorplan_model
        try:
            if self.cleaned_data['type'] != 'indoor' or self.cleaned_data['floorplan_selection'] == 'new':
                return None
        except KeyError:
            raise ValidationError(_("Please fill required fields"))
        pk = self.cleaned_data['floorplan']
        if not pk:
            raise ValidationError(_('No floorplan selected'))
        try:
            fl = floorplan_model.objects.get(pk=pk)
        except floorplan_model.DoesNotExist:
            raise ValidationError(_('Selected floorplan does not exist'))
        if fl.location != self.cleaned_data['location']:
            raise ValidationError(_('This floorplan is associated to a different location'))
        return fl

    def clean(self):
        data = self.cleaned_data
        try:
            type_ = data['type']
        except KeyError:
            raise ValidationError(_("Please fill required field"))
        is_mobile = data['is_mobile']
        msg = _('this field is required for locations of type %(type)s')
        fields = []
        if not is_mobile and type_ in ['outdoor', 'indoor']:
            fields += ['location_selection', 'name', 'address', 'geometry']
        if not is_mobile and type_ == 'indoor':
            fields += ['floorplan_selection', 'floor', 'indoor']
            if data.get('floorplan_selection') == 'existing':
                fields.append('floorplan')
            elif data.get('floorplan_selection') == 'new':
                fields.append('image')
        elif is_mobile and not data.get('location'):
            data['name'] = ''
            data['address'] = ''
            data['geometry'] = ''
            data['location_selection'] = 'new'
        for field in fields:
            if field in data and data[field] in [None, '']:
                params = {'type': type_}
                err = ValidationError(msg, params=params)
                self.add_error(field, err)

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


# Prepend DeviceLocationInline to config.DeviceAdmin
DeviceAdmin.inlines.insert(0, DeviceLocationInline)
