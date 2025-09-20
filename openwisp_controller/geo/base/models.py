import re

from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django_loci.base.models import (
    AbstractFloorPlan,
    AbstractLocation,
    AbstractObjectLocation,
)
from swapper import get_model_name

from openwisp_controller.config.whois.service import WHOISService
from openwisp_users.mixins import OrgMixin, ValidateOrgMixin


class BaseLocation(OrgMixin, AbstractLocation):
    _changed_checked_fields = ["is_estimated", "address", "geometry"]

    is_estimated = models.BooleanField(
        default=False,
        help_text=_("Whether the location's coordinates are estimated."),
    )

    class Meta(AbstractLocation.Meta):
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_initial_values_for_changed_checked_fields()

    def _set_initial_values_for_changed_checked_fields(self):
        deferred_fields = self.get_deferred_fields()
        for field in self._changed_checked_fields:
            if field in deferred_fields:
                setattr(self, f"_initial_{field}", models.DEFERRED)
            else:
                setattr(self, f"_initial_{field}", getattr(self, field))

    def clean(self):
        # Raise validation error if `is_estimated` is True but estimated feature is
        # disabled.
        if (
            (self._state.adding or self._initial_is_estimated != self.is_estimated)
            and self.is_estimated
            and not WHOISService.check_estimate_location_configured(
                self.organization_id
            )
        ):
            raise ValidationError(
                {
                    "is_estimated": _(
                        "Estimated Location feature required to be configured."
                    )
                }
            )
        return super().clean()

    def save(self, *args, _set_estimated=False, **kwargs):
        """
        Save the location object with special handling for estimated locations.

        Parameters:
            _set_estimated: Boolean flag to indicate if this save is being performed
            by the estimated location system. When False (default),
            manual edits will clear the estimated status.
            *args, **kwargs: Arguments passed to the parent save method.

        Returns:
            The result of the parent save method.
        """
        if WHOISService.check_estimate_location_configured(self.organization_id):
            if not _set_estimated and (
                self._initial_address != self.address
                or self._initial_geometry != self.geometry
            ):
                self.is_estimated = False
                estimated_string = gettext("Estimated Location")
                if self.name and estimated_string in self.name:
                    # remove string starting with "(Estimated Location"
                    self.name = re.sub(
                        rf"\s\({estimated_string}.*", "", self.name, flags=re.IGNORECASE
                    )
        else:
            self.is_estimated = self._initial_is_estimated
        return super().save(*args, **kwargs)


class BaseFloorPlan(OrgMixin, AbstractFloorPlan):
    location = models.ForeignKey(get_model_name("geo", "Location"), models.CASCADE)

    class Meta(AbstractFloorPlan.Meta):
        abstract = True

    def clean(self):
        if not hasattr(self, "location"):
            return
        self.organization = self.location.organization
        self._validate_org_relation("location")
        super().clean()


class BaseDeviceLocation(ValidateOrgMixin, AbstractObjectLocation):
    # remove generic foreign key attributes
    # (we use a direct foreign key to Device)
    content_type = None
    object_id = None

    # reuse the same generic attribute name used in django-loci
    content_object = models.OneToOneField(
        get_model_name("config", "Device"), models.CASCADE
    )
    # override parent foreign key targets
    location = models.ForeignKey(
        get_model_name("geo", "Location"), models.CASCADE, blank=True, null=True
    )
    floorplan = models.ForeignKey(
        get_model_name("geo", "FloorPlan"), models.CASCADE, blank=True, null=True
    )

    class Meta(AbstractObjectLocation.Meta):
        abstract = True
        # remove AbstractObjectLocation.Meta.unique_together
        unique_together = None

    def clean(self):
        self._validate_org_relation("location", field_error="location")
        self._validate_org_relation("floorplan", field_error="floorplan")
        super().clean()

    @property
    def device(self):
        return self.content_object

    @property
    def organization_id(self):
        return self.device.organization_id
