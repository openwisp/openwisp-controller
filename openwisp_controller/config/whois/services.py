from ipaddress import ip_address

from django.core.cache import cache
from django.db import transaction
from swapper import load_model

from openwisp_controller.config.settings import WHOIS_ENABLED

from .tasks import fetch_whois_details


class WhoIsService:
    """
    A handler class for managing the WhoIs functionality.
    """

    # slots are used to define a fixed set of attributes for the class,
    # which can improve performance by avoiding the overhead of a dynamic dictionary.
    # Particularly useful in scenarios where many instances of the class are created.
    # Reference: https://wiki.python.org/moin/UsingSlots
    __slots__ = ("device", "org_settings")

    _CACHE_KEY_KEY = "whois_info:{ip_address}"

    def __init__(self, device):
        self.device = device
        self.org_settings = device._get_organization__config_settings()

    def _need_whois_lookup(self, initial_ip, new_ip):
        """
        Returns True if the WhoIs lookup is needed.
        This is used to determine if the WhoIs lookup should be triggered
        when the device is saved.

        The lookup is triggered if:
            - WhoIs is enabled in the organization settings.
            - The new IP address is not None.
            - The WhoIs information is not already present or the initial IP is
              different from the new IP.
            - The new IP address is a global (public) IP address.
        """
        whois_info = self.get_whois_info()
        return (
            getattr(self.org_settings, "whois_enabled", WHOIS_ENABLED)
            and new_ip
            and (not whois_info or initial_ip != new_ip)
            and ip_address(new_ip).is_global
        )

    def trigger_whois_lookup(self):
        """
        Trigger WhoIs lookup based on the conditions of `_need_whois_lookup`.
        Task is triggered on commit to ensure redundant data is not created.
        """
        if self._need_whois_lookup(self.device._initial_last_ip, self.device.last_ip):
            transaction.on_commit(
                lambda: fetch_whois_details.delay(
                    device_pk=self.device.pk,
                    initial_ip_address=self.device._initial_last_ip,
                    new_ip_address=self.device.last_ip,
                )
            )

    def get_whois_info(self):
        """
        Returns WhoIsInfo for the device if WhoIs is enabled and IP is valid public ip.
        Results are cached to avoid repeated lookups for the same IP address.
        """
        WhoIsInfo = load_model("config", "WhoIsInfo")

        if not getattr(self.org_settings, "whois_enabled", WHOIS_ENABLED):
            return None

        ip = self.device.last_ip
        if not ip or not ip_address(ip).is_global:
            return None

        key = self._CACHE_KEY_KEY.format(ip_address=ip)
        whois_info = cache.get(key)
        if whois_info is not None:
            return whois_info

        whois_info = WhoIsInfo.objects.filter(ip_address=ip).first()
        if whois_info:
            cache.set(key, whois_info, timeout=60 * 60 * 24)  # Cache for 24 hours
        return whois_info

    # The function is staticmethod because it does not depend on the instance
    # of the class and deletes the WhoIs record for a given IP address.
    @staticmethod
    def delete_whois_record(ip_address):
        """
        Deletes the WhoIs record for the device's last IP address and invalidate
        the cache for that IP address.
        This is used when the device is deleted or its last IP address is changed.
        """
        WhoIsInfo = load_model("config", "WhoIsInfo")

        key = WhoIsService._CACHE_KEY_KEY.format(ip_address=ip_address)
        queryset = WhoIsInfo.objects.filter(ip_address=ip_address)
        if queryset.exists():
            queryset.delete()
            cache.delete(key)
