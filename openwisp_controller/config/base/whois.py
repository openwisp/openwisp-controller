from ipaddress import ip_address, ip_network

from django.contrib.gis.db.models import PointField
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from swapper import load_model

from openwisp_utils.base import TimeStampedEditableModel

from ..whois.service import WHOISService


class AbstractWHOISInfo(TimeStampedEditableModel):
    """
    Abstract model to store WHOIS information
    for a device.
    """

    id = None
    # Using ip_address as primary key to avoid redundant lookups
    # and storage of duplicate WHOIS information per IP address.
    # When a device's last IP address changes, data for the previous IP
    # is retained temporarily in case a device returns to it later.
    ip_address = models.GenericIPAddressField(db_index=True, primary_key=True)
    isp = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Organization for ASN"),
    )
    asn = models.CharField(
        max_length=10,
        blank=True,
        help_text=_("ASN"),
    )
    timezone = models.CharField(
        max_length=35,
        blank=True,
        help_text=_("Time zone"),
    )
    address = models.JSONField(
        default=dict,
        help_text=_("Address"),
        blank=True,
    )
    cidr = models.CharField(
        max_length=49,
        blank=True,
        help_text=_("CIDR"),
    )
    coordinates = PointField(
        null=True,
        blank=True,
        help_text=_("Coordinates"),
        srid=4326,
    )
    unreferenced_since = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        db_index=True,
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
                ) from e
        if self.coordinates:
            if not (-90 <= self.coordinates.y <= 90):
                raise ValidationError(
                    {"coordinates": _("Latitude must be between -90 and 90 degrees.")}
                )
            if not (-180 <= self.coordinates.x <= 180):
                raise ValidationError(
                    {
                        "coordinates": _(
                            "Longitude must be between -180 and 180 degrees."
                        )
                    }
                )
        return super().clean()

    @classmethod
    def update_reference_state(cls, ip_addresses):
        """Flag WHOIS IPs as referenced or record when they became unreferenced."""
        Device = load_model("config", "Device")
        ip_addresses = {
            WHOISService.normalize_ip_address(ip_address)
            for ip_address in ip_addresses
            if WHOISService.is_valid_public_ip_address(ip_address)
        }
        if not ip_addresses:
            return
        active_ips = set(
            Device.objects.filter(
                _is_deactivated=False, last_ip__in=ip_addresses
            ).values_list("last_ip", flat=True)
        )
        if active_ips:
            cls.objects.filter(ip_address__in=active_ips).update(
                unreferenced_since=None
            )
        orphaned_ips = ip_addresses - active_ips
        if orphaned_ips:
            cls.objects.filter(
                ip_address__in=orphaned_ips, unreferenced_since__isnull=True
            ).update(unreferenced_since=timezone.now())

    @staticmethod
    def device_whois_info_delete_handler(instance, **kwargs):
        """
        Flag WHOIS information as unreferenced when a device is deleted.
        """
        last_ip = instance.last_ip
        if last_ip:
            transaction.on_commit(
                lambda: instance._meta.model.update_reference_state([last_ip])
            )

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

    @property
    def _location_name(self):
        """
        Used to get location name based on the address and IP.
        """
        address = self.formatted_address
        if address:
            parts = [part.strip() for part in address.split(",")[:2] if part.strip()]
            location = ", ".join(parts)
            # Use named placeholders so translators receive the template
            return _("%(location)s: %(ip)s") % {
                "location": location,
                "ip": self.ip_address,
            }
        # Use named placeholder for consistency
        return _("Estimated Location: %(ip)s") % {"ip": self.ip_address}
