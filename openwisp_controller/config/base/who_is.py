from ipaddress import ip_address, ip_network

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from jsonfield import JSONField

from openwisp_utils.base import TimeStampedEditableModel

from ..who_is.service import WhoIsService


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
        if self.cidr:
            try:
                # strict is set to False to allow CIDR without a mask
                # e.g. 192.168.1.12/24 with strict False normalizes to
                # 192.168.1.0/24 else it would raise an error.
                ip_network(self.cidr, strict=False)
            except ValueError as e:
                raise ValidationError(
                    _("Invalid CIDR format: %(error)s") % {"error": str(e)}
                )
        return super().clean()

    @staticmethod
    def device_who_is_info_delete_handler(instance, **kwargs):
        """
        Delete WhoIs information for a device when the last IP address is removed or
        when device is deleted.
        """
        transaction.on_commit(
            lambda: WhoIsService.delete_who_is_record.delay(instance.last_ip)
        )

    # this method is kept here instead of in OrganizationConfigSettings because
    # currently the caching is used only for WhoIs feature
    @staticmethod
    def invalidate_org_settings_cache(instance, **kwargs):
        """
        Invalidate the cache for Organization settings on update/delete of
        Organization settings instance.
        """
        org_id = instance.organization_id
        cache.delete(WhoIsService.get_cache_key(org_id))

    @property
    def get_address(self):
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
