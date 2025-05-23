from django.db import models
from django.utils.translation import gettext_lazy as _
from swapper import get_model_name

from openwisp_utils.base import TimeStampedEditableModel


class AbstractWHOISInfo(TimeStampedEditableModel):
    """
    Abstract model to store WHOIS information
    for a device.
    """

    device = models.OneToOneField(
        get_model_name("config", "Device"),
        on_delete=models.CASCADE,
        related_name="whois_info",
        help_text=_("Device to which this WHOIS info belongs"),
    )
    last_public_ip = models.GenericIPAddressField(
        db_index=True,
        help_text=_(
            "indicates the IP address logged from "
            "the last request coming from the device"
        ),
    )
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
    address = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Address"),
    )
    cidr = models.CharField(
        max_length=20,
        blank=True,
        help_text=_("CIDR"),
    )

    class Meta:
        abstract = True
