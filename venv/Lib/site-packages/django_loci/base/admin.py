import json
from functools import partialmethod

from django import forms
from django.contrib import admin
from django.contrib.admin import widgets
from django.contrib.admin.sites import site
from django.contrib.contenttypes.admin import GenericStackedInline
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from leaflet.admin import LeafletGeoAdmin

from openwisp_utils.admin import TimeReadonlyAdminMixin

from ..base.geocoding_views import geocode_view, reverse_geocode_view
from ..fields import GeometryField
from ..widgets import FloorPlanWidget, ImageWidget
from .models import AbstractFloorPlan, AbstractLocation


class ReadOnlyMixin:
    """Mixin for forms to handle field widgets for view-only users."""

    def set_readonly_attribute(self, user, fields):
        """
        This method sets the read_only attribute on widget for the fields
        which are required to be rendered as it is to view-only users. This is
        done as 'AdminReadonlyField' renders the widget if 'read_only' is set on
        the field's widget. Also the required field must be present in self.fields
        """
        app_label = self.Meta.model._meta.app_label
        model_name = self.Meta.model._meta.model_name
        if (
            user
            and user.has_perm(f"{app_label}.view_{model_name}")
            and not user.has_perm(f"{app_label}.change_{model_name}")
        ):
            for field in fields:
                if field in self.fields:
                    setattr(self.fields[field].widget, "read_only", True)
            # Return 'True' to allow any further handling for view-only users
            return True
        return False


class AbstractFloorPlanForm(ReadOnlyMixin, forms.ModelForm):
    # define the image field to add it in self.fields
    # to render it for view-only
    image = forms.ImageField(
        widget=ImageWidget(),
        help_text=AbstractFloorPlan._meta.get_field("image").help_text,
    )

    class Meta:
        exclude = tuple()

    class Media:
        css = {"all": ("django-loci/css/loci.css",)}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if getattr(self, "_user", None):
            self.set_readonly_attribute(self._user, ["image"])
            # user is set on Form class which gets instantiated for each request
            del self.__class__._user


class LocationRawIdWidget(widgets.ForeignKeyRawIdWidget):
    """
    When selecting a location object
    via a popup window in the floorplan
    admin add view, display only indoor locations
    """

    def url_parameters(self):
        url_params = super().url_parameters()
        url_params["type__exact"] = "indoor"
        return url_params


class AbstractFloorPlanAdmin(TimeReadonlyAdminMixin, admin.ModelAdmin):
    list_display = ["__str__", "location", "floor", "created", "modified"]
    list_select_related = ["location"]
    search_fields = ["location__name"]
    raw_id_fields = ["location"]
    save_on_top = True

    def get_form(self, request, obj=None, **kwargs):
        form = super(AbstractFloorPlanAdmin, self).get_form(request, obj, **kwargs)
        permissions = self.get_model_perms(request)
        # location field is not in base_fields if user has only view-only permission
        if permissions["add"] and permissions["change"] and permissions["delete"]:
            form.base_fields["location"].widget = LocationRawIdWidget(
                rel=self.model._meta.get_field("location").remote_field, admin_site=site
            )
        # pass user to form for handling permissions for readonly view
        form._user = request.user
        return form


class AbstractLocationForm(ReadOnlyMixin, forms.ModelForm):
    # define the geometry field to add it in self.fields
    # to render it for view-only
    geometry = GeometryField(required=False)

    class Meta:
        exclude = tuple()

    class Media:
        js = (
            "admin/js/jquery.init.js",
            "django-loci/js/loci.js",
            "django-loci/js/floorplan-inlines.js",
            "django-loci/js/vendor/reconnecting-websocket.min.js",
        )
        css = {"all": ("django-loci/css/loci.css",)}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if getattr(self, "_user", None):
            self.set_readonly_attribute(self._user, ["geometry"])
            # user is set on Form class which gets instantiated for each request
            del self.__class__._user


class AbstractFloorPlanInline(TimeReadonlyAdminMixin, admin.StackedInline):
    extra = 0
    ordering = ("floor",)


class AbstractLocationAdmin(TimeReadonlyAdminMixin, LeafletGeoAdmin):
    list_display = ["name", "short_type", "is_mobile", "created", "modified"]
    search_fields = ["name", "address"]
    list_filter = ["type", "is_mobile"]
    save_on_top = True

    # This allows apps which extend django-loci to load this template with less hacks
    change_form_template = "admin/django_loci/location_change_form.html"

    # override get_form method to pass user to form
    # for handling permissions for readonly view
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form._user = request.user
        return form

    def get_urls(self):
        # hardcoding django_loci as the prefix for the
        # view names makes it much easier to extend
        # without having to change templates
        app_label = "django_loci"
        return [
            path(
                "<uuid:pk>/json/",
                self.admin_site.admin_view(self.json_view),
                name="{0}_location_json".format(app_label),
            ),
            path(
                "<uuid:pk>/floorplans/json/",
                self.admin_site.admin_view(self.floorplans_json_view),
                name="{0}_location_floorplans_json".format(app_label),
            ),
            path(
                "geocode/",
                self.admin_site.admin_view(geocode_view),
                name="{0}_location_geocode_api".format(app_label),
            ),
            path(
                "reverse-geocode/",
                self.admin_site.admin_view(reverse_geocode_view),
                name="{0}_location_reverse_geocode_api".format(app_label),
            ),
        ] + super().get_urls()

    def json_view(self, request, pk):
        instance = get_object_or_404(self.model, pk=pk)
        return JsonResponse(
            {
                "name": instance.name,
                "type": instance.type,
                "is_mobile": instance.is_mobile,
                "address": instance.address,
                "geometry": (
                    json.loads(instance.geometry.json) if instance.geometry else None
                ),
            }
        )

    def floorplans_json_view(self, request, pk):
        instance = get_object_or_404(self.model, pk=pk)
        choices = []
        for floorplan in instance.floorplan_set.all():
            choices.append(
                {
                    "id": floorplan.pk,
                    "str": str(floorplan),
                    "floor": floorplan.floor,
                    "image": floorplan.image.url,
                    "image_width": floorplan.image.width,
                    "image_height": floorplan.image.height,
                }
            )
        return JsonResponse({"choices": choices})

    def get_formset_kwargs(self, request, obj, inline, prefix):
        formset_kwargs = super().get_formset_kwargs(request, obj, inline, prefix)
        # manually set TOTAL_FORMS to 0 if the type is outdoor to avoid floorplan form creation
        if request.method == "POST" and formset_kwargs["data"]["type"] == "outdoor":
            formset_kwargs["data"]["floorplan_set-TOTAL_FORMS"] = "0"
        return formset_kwargs


class UnvalidatedChoiceField(forms.ChoiceField):
    """
    skips ChoiceField validation to allow custom options
    """

    def validate(self, value):
        super(forms.ChoiceField, self).validate(value)


_get_field = AbstractLocation._meta.get_field


class AbstractObjectLocationForm(ReadOnlyMixin, forms.ModelForm):
    FORM_CHOICES = (
        ("", _("--- Please select an option ---")),
        ("new", _("New")),
        ("existing", _("Existing")),
    )
    LOCATION_TYPES = (
        FORM_CHOICES[0],
        AbstractLocation.LOCATION_TYPES[0],
        AbstractLocation.LOCATION_TYPES[1],
    )
    location_selection = forms.ChoiceField(choices=FORM_CHOICES, required=False)
    name = forms.CharField(
        label=_("Location name"),
        max_length=75,
        required=False,
        help_text=_get_field("name").help_text,
    )
    address = forms.CharField(max_length=128, required=False)
    type = forms.ChoiceField(
        choices=LOCATION_TYPES, required=True, help_text=_get_field("type").help_text
    )
    is_mobile = forms.BooleanField(
        label=_get_field("is_mobile").verbose_name,
        help_text=_get_field("is_mobile").help_text,
        required=False,
    )
    geometry = GeometryField(required=False)
    floorplan_selection = forms.ChoiceField(required=False, choices=FORM_CHOICES)
    floorplan = UnvalidatedChoiceField(
        choices=((None, FORM_CHOICES[0][1]),), required=False
    )
    floor = forms.IntegerField(required=False)
    image = forms.ImageField(
        required=False,
        widget=ImageWidget(thumbnail=False),
        help_text=_("floor plan image"),
    )
    indoor = forms.CharField(
        max_length=64,
        required=False,
        label=_("indoor position"),
        widget=FloorPlanWidget,
    )

    class Meta:
        exclude = tuple()

    class Media:
        js = (
            "admin/js/jquery.init.js",
            "django-loci/js/loci.js",
            "django-loci/js/floorplan-widget.js",
            "django-loci/js/vendor/reconnecting-websocket.min.js",
        )
        css = {
            "all": ("django-loci/css/loci.css", "django-loci/css/floorplan-widget.css")
        }

    def __init__(self, *args, **kwargs):
        # user is passed via partialmethod in ObjectLocationInline
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        # set initial values for custom fields
        initial = {}
        location = self._get_initial_location()
        floorplan = self._get_initial_floorplan()
        if location:
            initial.update(
                {
                    "location_selection": "existing",
                    "type": location.type,
                    "is_mobile": location.is_mobile,
                    "name": location.name,
                    "address": location.address,
                    "geometry": location.geometry,
                }
            )
        if floorplan:
            initial.update(
                {
                    "floorplan_selection": "existing",
                    "floorplan": floorplan.pk,
                    "floor": floorplan.floor,
                    "image": floorplan.image,
                }
            )
            floorplan_choices = self.fields["floorplan"].choices
            self.fields["floorplan"].choices = floorplan_choices + [
                (floorplan.pk, floorplan)
            ]

        if self.set_readonly_attribute(user, ["geometry", "image", "indoor"]):
            # For view only permissions, 'AdminReadonlyField' reads from instance
            for field, value in initial.items():
                if field != "floorplan":
                    setattr(self.instance, field, value)
                else:
                    setattr(self.instance.floorplan, "pk", value)
            # Added id to indoor widget to display indoor position
            self.fields["indoor"].widget.attrs.update({"id": "id_indoor"})
        self.initial.update(initial)

    def _get_initial_location(self):
        return self.instance.location

    def _get_initial_floorplan(self):
        return self.instance.floorplan

    @cached_property
    def floorplan_model(self):
        return self.Meta.model.floorplan.field.remote_field.model

    @cached_property
    def location_model(self):
        return self.Meta.model.location.field.remote_field.model

    def clean_floorplan(self):
        floorplan_model = self.floorplan_model
        type_ = self.cleaned_data.get("type")
        floorplan_selection = self.cleaned_data.get("floorplan_selection")
        if type_ != "indoor" or floorplan_selection == "new" or not floorplan_selection:
            return None
        pk = self.cleaned_data["floorplan"]
        if not pk:
            raise ValidationError(_("No floorplan selected"))
        try:
            fl = floorplan_model.objects.get(pk=pk)
        except floorplan_model.DoesNotExist:
            raise ValidationError(_("Selected floorplan does not exist"))
        if fl.location != self.cleaned_data["location"]:
            raise ValidationError(
                _("This floorplan is associated to a different location")
            )
        return fl

    def clean(self):
        data = self.cleaned_data
        type_ = data.get("type")
        is_mobile = data["is_mobile"]
        msg = _("this field is required for locations of type %(type)s")
        fields = []
        if not is_mobile and type_ in ["outdoor", "indoor"]:
            fields += ["location_selection", "name", "address", "geometry"]
        # sync location, clean indoor field basis type
        if location := data.get("location"):
            location.type = type_
            data["indoor"] = None if type_ != "indoor" else data.get("indoor")
        if type_ == "indoor":
            if data.get("floorplan_selection") == "existing":
                fields.append("floorplan")
            if data.get("image"):
                fields += ["floor", "indoor"]
        elif is_mobile and not data.get("location"):
            data["name"] = ""
            data["address"] = ""
            data["geometry"] = ""
            data["location_selection"] = "new"
        for field in fields:
            if field in data and data[field] in [None, ""]:
                params = {"type": type_}
                err = ValidationError(msg, params=params)
                self.add_error(field, err)

    def _get_location_instance(self):
        data = self.cleaned_data
        location = data.get("location") or self.location_model()
        location.type = data.get("type") or location.type
        location.is_mobile = data.get("is_mobile", location.is_mobile)
        location.name = data.get("name") or location.name
        location.address = data.get("address") or location.address
        location.geometry = data.get("geometry") or location.geometry
        return location

    def _get_floorplan_instance(self):
        data = self.cleaned_data
        instance = self.instance
        floorplan = data.get("floorplan") or self.floorplan_model()
        floorplan.location = instance.location
        floorplan.floor = data.get("floor")
        # the image path is updated only during creation
        # or if the image has been actually changed
        if data.get("image") and self.initial.get("image") != data.get("image"):
            floorplan.image = data["image"]
        return floorplan

    def save(self, commit=True):
        instance = self.instance
        data = self.cleaned_data
        # create or update location
        instance.location = self._get_location_instance()
        # set name of mobile locations automatically
        if data["is_mobile"] and not instance.location.name:
            instance.location.name = str(self.instance.content_object)
        instance.location.save()
        # create or update floorplan
        floorplan = self._get_floorplan_instance()
        if data["type"] == "indoor" and floorplan.image:
            instance.floorplan = floorplan
            instance.floorplan.save()
        # call super
        return super().save(commit=True)


class ObjectLocationMixin(TimeReadonlyAdminMixin):
    """
    Base ObjectLocationInline logic, can be imported and
    mixed in with different inline classes (stacked, tabular).
    If you need the generic inline look below.
    """

    verbose_name = _("geographic information")
    verbose_name_plural = verbose_name
    raw_id_fields = ("location",)
    max_num = 1
    extra = 1
    template = "admin/django_loci/location_inline.html"
    fieldsets = (
        (None, {"fields": ("location_selection",)}),
        (
            "Geographic coordinates",
            {
                "classes": ("loci", "coords"),
                "fields": (
                    "location",
                    "type",
                    "is_mobile",
                    "name",
                    "address",
                    "geometry",
                ),
            },
        ),
        (
            "Indoor coordinates",
            {
                "classes": ("indoor", "coords"),
                "fields": (
                    "floorplan_selection",
                    "floorplan",
                    "floor",
                    "image",
                    "indoor",
                ),
            },
        ),
    )

    # override get_formset method to pass user to form
    def get_formset(self, request, obj=..., **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset._construct_form = partialmethod(
            formset._construct_form, user=request.user
        )
        return formset


class AbstractObjectLocationInline(ObjectLocationMixin, GenericStackedInline):
    """
    Generic Inline + ObjectLocationMixin
    """
