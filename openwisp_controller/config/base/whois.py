from ipaddress import ip_address

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from jsonfield import JSONField
from swapper import get_model_name

from openwisp_utils.base import TimeStampedEditableModel

from ..settings import WHOIS_ENABLED


class AbstractWhoIsInfo(TimeStampedEditableModel):
    """
    Abstract model to store WhoIs information
    for a device.
    """

    device = models.OneToOneField(
        get_model_name("config", "Device"),
        on_delete=models.CASCADE,
        related_name="whois_info",
        help_text=_("Device to which this WhoIs info belongs"),
    )
    ip_address = models.GenericIPAddressField(db_index=True)
    organization_name = models.CharField(
        max_length=200,
        blank=True,
        help_text=_("Organization name"),
    )
    country = models.CharField(
        max_length=4,
        blank=True,
        help_text=_("Country Code"),
    )
    asn = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Autonomous System Number"),
    )
    timezone = models.CharField(
        max_length=100,
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

    def save(self, *args, **kwargs):
        org_settings = self.device._get_organization__config_settings()
        if not getattr(org_settings, "whois_enabled", WHOIS_ENABLED):
            raise ValueError(
                _("WhoIs information creation is disabled for this organization.")
            )
        return super().save(*args, **kwargs)
