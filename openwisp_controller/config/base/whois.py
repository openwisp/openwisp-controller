from ipaddress import ip_address

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from jsonfield import JSONField

from openwisp_utils.base import TimeStampedEditableModel


class AbstractWhoIsInfo(TimeStampedEditableModel):
    """
    Abstract model to store WhoIs information
    for a device.
    """

    id = None
    ip_address = models.GenericIPAddressField(db_index=True, primary_key=True)
    organization_name = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Organization name"),
    )
    country = models.CharField(
        max_length=4,
        blank=True,
        help_text=_("Country Code"),
    )
    asn = models.CharField(
        max_length=6,
        blank=True,
        help_text=_("Autonomous System Number"),
    )
    timezone = models.CharField(
        max_length=35,
        blank=True,
        help_text=_("Time zone"),
    )
    address = JSONField(
        default=dict,
        help_text=_("Address"),
        blank=True,
    )
    cidr = models.CharField(
        max_length=20,
        blank=True,
        help_text=_("CIDR"),
    )

    class Meta:
        abstract = True

    def clean(self):
        if ip_address(self.ip_address).is_private:
            raise ValidationError(
                _("WhoIs information cannot be created for private IP addresses.")
            )
        return super().clean()
