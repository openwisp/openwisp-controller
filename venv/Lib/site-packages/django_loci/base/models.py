import logging

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models
from django.contrib.humanize.templatetags.humanize import ordinal
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from openwisp_utils.base import TimeStampedEditableModel

from .. import settings as app_settings

logger = logging.getLogger(__name__)


class AbstractLocation(TimeStampedEditableModel):
    LOCATION_TYPES = (
        ("outdoor", _("Outdoor environment (eg: street, square, garden, land)")),
        (
            "indoor",
            _("Indoor environment (eg: building, roofs, subway, large vehicles)"),
        ),
    )
    name = models.CharField(
        _("name"),
        max_length=75,
        help_text=_(
            "A descriptive name of the location " "(building name, company name, etc.)"
        ),
    )
    type = models.CharField(
        choices=LOCATION_TYPES,
        max_length=8,
        db_index=True,
        help_text=_("indoor locations can have floorplans associated to them"),
    )
    is_mobile = models.BooleanField(
        _("is mobile?"),
        default=False,
        db_index=True,
        help_text=_("is this location a moving object?"),
    )
    address = models.CharField(_("address"), db_index=True, max_length=256, blank=True)
    geometry = models.GeometryField(_("geometry"), blank=True, null=True)

    class Meta:
        abstract = True

    # overriding __init__ to store the initial type
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initial_type = self.type

    def __str__(self):
        return self.name

    def clean(self):
        self._validate_geometry_if_not_mobile()

    def _validate_geometry_if_not_mobile(self):
        """
        geometry can be NULL, but only if_mobile is True
        otherwise raise a ValidationError
        """
        if not self.is_mobile and not self.geometry:
            raise ValidationError({"geometry": _("No geometry value provided.")})

    @property
    def short_type(self):
        return _(self.type.capitalize())

    # save method is automatically wrapped in atomic transaction
    def save(self, *args, **kwargs):
        # if location type is changed to outdoor, remove all associated floorplans
        if (
            self.type != self._initial_type
            and not self._state.adding
            and self.type == "outdoor"
            and self.floorplan_set.exists()
        ):
            self.objectlocation_set.update(floorplan=None, indoor=None)
            self.floorplan_set.all().delete()
        return super().save(*args, **kwargs)


class AbstractFloorPlan(TimeStampedEditableModel):
    location = models.ForeignKey("django_loci.Location", on_delete=models.CASCADE)
    floor = models.SmallIntegerField(_("floor"))
    image = models.ImageField(
        _("image"),
        upload_to=app_settings.FLOORPLAN_STORAGE.upload_to,
        storage=app_settings.FLOORPLAN_STORAGE(),
        help_text=_("floor plan image"),
    )

    class Meta:
        abstract = True
        unique_together = ("location", "floor")

    def __str__(self):
        if self.floor != 0:
            suffix = _("{0} floor").format(ordinal(self.floor))
        else:
            suffix = _("ground floor")
        return "{0} {1}".format(self.location.name, suffix)

    def clean(self):
        self._validate_location_type()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self._remove_image()

    def _validate_location_type(self):
        if not hasattr(self, "location") or not hasattr(self.location, "type"):
            return
        if self.location.type and self.location.type != "indoor":
            msg = "floorplans can only be associated " 'to locations of type "indoor"'
            raise ValidationError(msg)

    def _remove_image(self):
        path = self.image.name
        if self.image.storage.exists(path):
            self.image.delete(save=False)
        else:
            msg = "floorplan image not found while deleting {0}:\n{1}"
            logger.error(msg.format(self, path))


class AbstractObjectLocation(TimeStampedEditableModel):
    LOCATION_TYPES = (
        ("outdoor", _("Outdoor")),
        ("indoor", _("Indoor")),
        ("mobile", _("Mobile")),
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=36, db_index=True)
    content_object = GenericForeignKey("content_type", "object_id")
    location = models.ForeignKey(
        "django_loci.Location", models.PROTECT, blank=True, null=True
    )
    floorplan = models.ForeignKey(
        "django_loci.Floorplan", models.PROTECT, blank=True, null=True
    )
    indoor = models.CharField(
        _("indoor position"), max_length=64, blank=True, null=True
    )

    class Meta:
        abstract = True
        unique_together = ("content_type", "object_id")

    def _clean_indoor_location(self):
        """
        ensures related floorplan is not
        associated to a different location
        """
        # skip validation if the instance does not
        # have a floorplan assigned to it yet
        if not self.location or self.location.type != "indoor" or not self.floorplan:
            return
        if self.location != self.floorplan.location:
            raise ValidationError(
                _("Invalid floorplan (belongs to a different location)")
            )

    def _raise_invalid_indoor(self):
        raise ValidationError({"indoor": _("invalid value")})

    def _clean_indoor_position(self):
        """
        ensures invalid indoor position values
        cannot be inserted into the database
        """
        # stop here if location not defined yet
        # (other validation errors will be triggered)
        if not self.location:
            return
        # do not allow non empty values for outdoor locations
        if self.location.type != "indoor" and self.indoor not in [None, ""]:
            self._raise_invalid_indoor()
        # allow empty values for outdoor locations
        elif self.location.type != "indoor" and self.indoor in [None, ""]:
            return
        # allow empty values for indoor whose coordinates are not yet received
        elif (
            self.location.type == "indoor"
            and self.indoor in [None, ""]
            and not self.floorplan
        ):
            return
        # split indoor position
        position = []
        if self.indoor:
            position = self.indoor.split(",")
        # must have at least e elements
        if len(position) != 2:
            self._raise_invalid_indoor()
        # each member must be convertible to float
        else:
            for part in position:
                try:
                    float(part)
                except ValueError:
                    self._raise_invalid_indoor()

    def clean(self):
        self._clean_indoor_location()
        self._clean_indoor_position()
