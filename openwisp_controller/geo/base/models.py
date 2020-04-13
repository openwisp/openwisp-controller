from django.contrib.gis.db import models
from django_loci.base.models import (
    AbstractFloorPlan,
    AbstractLocation,
    AbstractObjectLocation,
)
from swapper import get_model_name

from openwisp_users.mixins import OrgMixin, ValidateOrgMixin


class BaseLocation(OrgMixin, AbstractLocation):
    class Meta(AbstractLocation.Meta):
        abstract = True


class BaseFloorPlan(OrgMixin, AbstractFloorPlan):
    location = models.ForeignKey(get_model_name('geo', 'Location'), models.CASCADE)

    class Meta(AbstractFloorPlan.Meta):
        abstract = True

    def clean(self):
        if not hasattr(self, 'location'):
            return
        self.organization = self.location.organization
        self._validate_org_relation('location')
        super().clean()


class BaseDeviceLocation(ValidateOrgMixin, AbstractObjectLocation):
    # remove generic foreign key attributes
    # (we use a direct foreign key to Device)
    content_type = None
    object_id = None

    # reuse the same generic attribute name used in django-loci
    content_object = models.OneToOneField(
        get_model_name('config', 'Device'), models.CASCADE
    )
    # override parent foreign key targets
    location = models.ForeignKey(
        get_model_name('geo', 'Location'), models.PROTECT, blank=True, null=True
    )
    floorplan = models.ForeignKey(
        get_model_name('geo', 'FloorPlan'), models.PROTECT, blank=True, null=True
    )

    class Meta(AbstractObjectLocation.Meta):
        abstract = True
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
