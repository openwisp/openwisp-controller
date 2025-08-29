from ipaddress import ip_address as ip_addr

from django.core.cache import cache
from django.db import transaction
from swapper import load_model

from openwisp_controller.config import settings as app_settings

from .tasks import fetch_whois_details, manage_estimated_locations


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
            return ip and ip_addr(ip).is_global
        except ValueError:
            return False

    @staticmethod
    def _get_whois_info_from_db(ip_address):
        """
        For getting existing WHOISInfo for given IP from db if present.
        """
        WHOISInfo = load_model("config", "WHOISInfo")

        return WHOISInfo.objects.filter(ip_address=ip_address)

    @staticmethod
    def get_org_config_settings(org_id):
        """
        Retrieve and cache organization-specific configuration settings.

        Returns a "read-only" OrganizationConfigSettings instance for the
        given organization.
        If no settings exist for the organization, returns an empty instance to allow
        fallback to global defaults.

        OrganizationConfigSettings are cached for performance, using the same timeout
        as DeviceChecksumView for consistency.
        """
        OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")
        Config = load_model("config", "Config")

        cache_key = WHOISService.get_cache_key(org_id=org_id)
        org_settings = cache.get(cache_key)
        if org_settings is None:
            try:
                org_settings = OrganizationConfigSettings.objects.get(
                    organization=org_id
                )
            except OrganizationConfigSettings.DoesNotExist:
                # If organization settings do not exist, fall back to global setting
                org_settings = OrganizationConfigSettings()
            cache.set(
                cache_key,
                org_settings,
                timeout=Config._CHECKSUM_CACHE_TIMEOUT,
            )
        return org_settings

    @staticmethod
    def check_estimate_location_configured(org_id):
        if not org_id:
            return False
        if not app_settings.WHOIS_CONFIGURED:
            return False
        org_settings = WHOISService.get_org_config_settings(org_id=org_id)
        return org_settings.estimated_location_enabled

    @property
    def is_whois_enabled(self):
        """
        Check if the WHOIS lookup feature is enabled.
        """
        org_settings = self.get_org_config_settings(org_id=self.device.organization.pk)
        return org_settings.whois_enabled

    @property
    def is_estimated_location_enabled(self):
        """
        Check if the Estimated location feature is enabled.
        """
        org_settings = self.get_org_config_settings(org_id=self.device.organization.pk)
        return org_settings.estimated_location_enabled

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

    def _need_estimated_location_management(self, new_ip):
        """
        Used to determine if Estimated locations need to be created/updated
        or not during WHOIS lookup.
        """
        if not self.is_valid_public_ip_address(new_ip):
            return False

        if not self.is_whois_enabled:
            return False

        return self.is_estimated_location_enabled

    def get_device_whois_info(self):
        """
        If the WHOIS lookup feature is enabled and the device ``last_ip``
        is a public IP, it fetches WHOIS information for the network device.
        """
        ip_address = self.device.last_ip
        if not (self.is_valid_public_ip_address(ip_address) and self.is_whois_enabled):
            return None

        return self._get_whois_info_from_db(ip_address=ip_address).first()

    def process_ip_data_and_location(self):
        """
        Trigger WHOIS lookup based on the conditions of `_need_whois_lookup`
        and also manage estimated locations based on the conditions of
        `_need_estimated_location_management`.
        Tasks are triggered on commit to ensure redundant data is not created.
        """
        new_ip = self.device.last_ip
        if self._need_whois_lookup(new_ip):
            transaction.on_commit(
                lambda: fetch_whois_details.delay(
                    device_pk=self.device.pk,
                    initial_ip_address=self.device._initial_last_ip,
                    new_ip_address=new_ip,
                )
            )
        # To handle the case when WHOIS already exists as in that case
        # WHOIS lookup is not triggered but we still need to
        # manage estimated locations.
        elif self._need_estimated_location_management(new_ip):
            transaction.on_commit(
                lambda: manage_estimated_locations.delay(
                    device_pk=self.device.pk, ip_address=new_ip
                )
            )
