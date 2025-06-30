from ipaddress import ip_address, ip_network

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from jsonfield import JSONField

from openwisp_utils.base import TimeStampedEditableModel

from ..whois.service import WHOISService
from ..whois.tasks import delete_whois_record


class AbstractWHOISInfo(TimeStampedEditableModel):
    """
    Abstract model to store WHOIS information
    for a device.
    """

    id = None
    # Using ip_address as primary key to avoid redundant lookups
    # and storage of duplicate WHOIS information per IP address.
    # Whenever a device's last ip address changes, data related to
    # previous IP address is deleted. If any device still has the
    # previous IP address, they will trigger the lookup again
    # ensuring latest WHOIS information is always available.
    ip_address = models.GenericIPAddressField(db_index=True, primary_key=True)
    isp = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Organization for ASN"),
    )
    asn = models.CharField(
        max_length=6,
        blank=True,
        help_text=_("ASN"),
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
                {
                    "ip_address": _(
                        "WHOIS information cannot be created for private IP addresses."
                    )
                }
            )
        if self.cidr:
            try:
                # strict is set to False to allow CIDR without a mask
                # e.g. 192.168.1.12/24 with strict False normalizes to
                # 192.168.1.0/24 else it would raise an error.
                ip_network(self.cidr, strict=False)
            except ValueError as e:
                raise ValidationError(
                    {"cidr": _("Invalid CIDR format: %(error)s") % {"error": str(e)}}
                )
        return super().clean()

    @staticmethod
    def device_whois_info_delete_handler(instance, **kwargs):
        """
        Delete WHOIS information for a device when the last IP address is removed or
        when device is deleted.
        """
        if instance._get_organization__config_settings().whois_enabled:
            transaction.on_commit(lambda: delete_whois_record.delay(instance.last_ip))

    # this method is kept here instead of in OrganizationConfigSettings because
    # currently the caching is used only for WHOIS feature
    @staticmethod
    def invalidate_org_settings_cache(instance, **kwargs):
        """
        Invalidate the cache for Organization settings on update/delete of
        Organization settings instance.
        """
        org_id = instance.organization_id
        cache.delete(WHOISService.get_cache_key(org_id))

    @property
    def formatted_address(self):
        """
        Used as default formatter for address field.
        'filter' is used to remove any None values
        """
        return ", ".join(
            filter(
                None,
                [
                    self.address.get("city"),
                    self.address.get("country"),
                    self.address.get("continent"),
                    self.address.get("postal"),
                ],
            )
        )
