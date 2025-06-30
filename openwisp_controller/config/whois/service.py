from ipaddress import ip_address

from django.core.cache import cache
from django.db import transaction
from swapper import load_model

from openwisp_controller.config import settings as app_settings

from .tasks import fetch_whois_details


class WHOISService:
    """
    A handler class for managing the WHOIS functionality.
    """

    def __init__(self, device):
        self.device = device

    @staticmethod
    def get_cache_key(org_id):
        """
        Used to get cache key for caching org settings of a device.
        """
        return f"organization_config_{org_id}"

    @staticmethod
    def is_valid_public_ip_address(ip):
        """
        Check if given IP address is a valid public IP address.
        """
        try:
            return ip and ip_address(ip).is_global
        except ValueError:
            return False

    @staticmethod
    def _get_whois_info_from_db(ip_address):
        """
        For getting existing WHOISInfo for given IP from db if present.
        """
        WHOISInfo = load_model("config", "WHOISInfo")

        return WHOISInfo.objects.filter(ip_address=ip_address)

    @property
    def is_whois_enabled(self):
        """
        Check if the WHOIS lookup feature is enabled.
        The OrganizationConfigSettings are cached as these settings
        are not expected to change frequently. The timeout for the cache
        is set to the same as the checksum cache timeout for consistency
        with DeviceChecksumView.
        """
        OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")
        Config = load_model("config", "Config")

        org_id = self.device.organization.pk
        org_settings = cache.get(self.get_cache_key(org_id=org_id))
        if org_settings is None:
            try:
                org_settings = OrganizationConfigSettings.objects.get(
                    organization=org_id
                )
            except OrganizationConfigSettings.DoesNotExist:
                # If organization settings do not exist, fall back to global setting
                return app_settings.WHOIS_ENABLED
            cache.set(
                self.get_cache_key(org_id=org_id),
                org_settings,
                timeout=Config._CHECKSUM_CACHE_TIMEOUT,
            )
        return getattr(org_settings, "whois_enabled", app_settings.WHOIS_ENABLED)

    def _need_whois_lookup(self, new_ip):
        """
        This is used to determine if the WHOIS lookup should be triggered
        when the device is saved.

        The lookup is not triggered if:
            - The new IP address is None or it is a private IP address.
            - The WHOIS information of new ip is already present.
            - WHOIS is disabled in the organization settings. (query from db)
        """

        # Check cheap conditions first before hitting the database
        if not self.is_valid_public_ip_address(new_ip):
            return False

        if self._get_whois_info_from_db(new_ip).exists():
            return False

        return self.is_whois_enabled

    def get_device_whois_info(self):
        """
        If the WHOIS lookup feature is enabled and the device ``last_ip``
        is a public IP, it fetches WHOIS information for the network device.
        """
        ip_address = self.device.last_ip
        if not (self.is_valid_public_ip_address(ip_address) and self.is_whois_enabled):
            return None

        return self._get_whois_info_from_db(ip_address=ip_address).first()

    def trigger_whois_lookup(self):
        """
        Trigger WHOIS lookup based on the conditions of `_need_whois_lookup`.
        Task is triggered on commit to ensure redundant data is not created.
        """
        if self._need_whois_lookup(self.device.last_ip):
            transaction.on_commit(
                lambda: fetch_whois_details.delay(
                    device_pk=self.device.pk,
                    initial_ip_address=self.device._initial_last_ip,
                    new_ip_address=self.device.last_ip,
                )
            )
