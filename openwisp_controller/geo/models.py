from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from django_loci.base.models import AbstractFloorPlan, AbstractLocation, AbstractObjectLocation

from openwisp_users.mixins import OrgMixin, ValidateOrgMixin


class Location(OrgMixin, AbstractLocation):
    class Meta(AbstractLocation.Meta):
        abstract = False

    def clean(self):
        if self.geometry is not None and not isinstance(self.geometry, Point):
            raise ValidationError({'geometry': _('Only point geometry is allowed')})
        super().clean()


class FloorPlan(OrgMixin, AbstractFloorPlan):
    location = models.ForeignKey(Location, models.CASCADE)

    class Meta(AbstractFloorPlan.Meta):
        abstract = False

    def clean(self):
        if not hasattr(self, 'location'):
            return
        self.organization = self.location.organization
        self._validate_org_relation('location')
        super().clean()


class DeviceLocation(ValidateOrgMixin, AbstractObjectLocation):
    # remove generic foreign key attributes
    # (we use a direct foreign key to Device)
    content_type = None
    object_id = None
    # reuse the same generic attribute name used in django-loci
    content_object = models.OneToOneField('config.Device', models.CASCADE)
    # override parent foreign key targets
    location = models.ForeignKey(Location, models.PROTECT,
                                 blank=True, null=True)
    floorplan = models.ForeignKey(FloorPlan, models.PROTECT,
                                  blank=True, null=True)

    class Meta(AbstractObjectLocation.Meta):
        abstract = False
        # remove AbstractObjectLocation.Meta.unique_together
        unique_together = None

    def clean(self):
        self._validate_org_relation('location', field_error='location')
        self._validate_org_relation('floorplan', field_error='floorplan')
        super().clean()

    @property
    def device(self):
        return self.content_object

    @property
    def organization_id(self):
        return self.device.organization_id


# maintain compatibility with django_loci
Location.objectlocation_set = Location.devicelocation_set
FloorPlan.objectlocation_set = FloorPlan.devicelocation_set
