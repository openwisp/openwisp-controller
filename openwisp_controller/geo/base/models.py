from typing import ClassVar

import swapper
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_loci.base.models import (
    AbstractFloorPlan,
    AbstractLocation,
    AbstractObjectLocation,
)
from swapper import get_model_name

from openwisp_controller.config import settings as config_app_settings
from openwisp_controller.geo import settings as geo_settings
from openwisp_controller.geo.estimated_location.service import EstimatedLocationService
from openwisp_users.mixins import OrgMixin, ValidateOrgMixin
from openwisp_utils.fields import FallbackBooleanChoiceField


class BaseLocation(OrgMixin, AbstractLocation):
    _changed_checked_fields: ClassVar[list[str]] = [
        "is_estimated",
        "address",
        "geometry",
    ]

    is_estimated = models.BooleanField(
        _("Is Estimated?"),
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
        estimated_status_changed = (
            self._initial_is_estimated is not models.DEFERRED
            and self._initial_is_estimated != self.is_estimated
        )
        if (
            (self._state.adding or estimated_status_changed)
            and self.is_estimated
            and not EstimatedLocationService.check_estimated_location_enabled(
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
            manual edits will clear the estimated status (only if estimated location
            feature is enabled).
            *args, **kwargs: Arguments passed to the parent save method.

        Returns:
            The result of the parent save method.
        """
        changed_fields = set()
        if EstimatedLocationService.check_estimated_location_enabled(
            self.organization_id
        ):
            address_changed = (
                self._initial_address is not models.DEFERRED
                and self._initial_address != self.address
            )
            geometry_changed = (
                self._initial_geometry is not models.DEFERRED
                and self._initial_geometry != self.geometry
            )
            if not _set_estimated and (address_changed or geometry_changed):
                self.is_estimated = False
                changed_fields = {"is_estimated"}
        # Manual changes to is_estimated discarded if feature not enabled
        elif self._initial_is_estimated is not models.DEFERRED:
            self.is_estimated = self._initial_is_estimated
            changed_fields = {"is_estimated"}
        if update_fields := kwargs.get("update_fields"):
            kwargs["update_fields"] = set(update_fields) | changed_fields
        result = super().save(*args, **kwargs)
        self._set_initial_values_for_changed_checked_fields()
        return result


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


class AbstractOrganizationGeoSettings(models.Model):
    organization = models.OneToOneField(
        swapper.get_model_name("openwisp_users", "Organization"),
        verbose_name=_("organization"),
        related_name="geo_settings",
        on_delete=models.CASCADE,
        primary_key=True,
    )
    estimated_location_enabled = FallbackBooleanChoiceField(
        help_text=_("Whether the estimated location feature is enabled"),
        fallback=geo_settings.ESTIMATED_LOCATION_ENABLED,
        verbose_name=_("Estimated Location Enabled"),
    )

    class Meta:
        verbose_name = _("Geographic settings")
        verbose_name_plural = verbose_name
        abstract = True

    def __str__(self):
        return _("Geo settings for %(organization)s") % {
            "organization": self.organization.name
        }

    def clean(self):
        if not config_app_settings.WHOIS_CONFIGURED and self.estimated_location_enabled:
            raise ValidationError(
                {
                    "estimated_location_enabled": _(
                        "WHOIS_GEOIP_ACCOUNT and WHOIS_GEOIP_KEY must be set "
                        "before enabling Estimated Location feature."
                    )
                }
            )
        config_settings = getattr(self.organization, "config_settings", None)
        if (
            config_settings
            and not config_settings.whois_enabled
            and self.estimated_location_enabled
        ):
            raise ValidationError(
                {
                    "estimated_location_enabled": _(
                        "The WHOIS feature must be enabled for this organization "
                        "before enabling the Estimated Location feature."
                    )
                }
            )

    @classmethod
    def organization_post_save_receiver(cls, sender, instance, created, **kwargs):
        """
        Create OrganizationGeoSettings when a new Organization is created.
        This signal handler is called when an Organization is saved.
        """
        if created:
            cls.objects.get_or_create(organization=instance)
