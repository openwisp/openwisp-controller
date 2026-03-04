from datetime import timedelta
from ipaddress import ip_address as ip_addr

import requests
from celery import current_app
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from geoip2 import errors
from geoip2 import webservice as geoip2_webservice
from swapper import load_model

from openwisp_controller.config import settings as app_settings

from .tasks import fetch_whois_details
from .utils import EXCEPTION_MESSAGES, send_whois_task_notification


class WHOISService:
    """
    A handler class for managing the WHOIS functionality.
    """

    def __init__(self, device):
        self.device = device

    @staticmethod
    def get_geoip_client():
        """
        Used to get a GeoIP2 web service client instance.
        Host is based on the db that is used to fetch the details.
        As we are using GeoLite2, 'geolite.info' host is used.
        Refer: https://geoip2.readthedocs.io/en/latest/#sync-web-service-example
        """
        return geoip2_webservice.Client(
            account_id=app_settings.WHOIS_GEOIP_ACCOUNT,
            license_key=app_settings.WHOIS_GEOIP_KEY,
            host="geolite.info",
        )

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
            # ip_address() from the stdlib raises ValueError for malformed strings
            return False

    @staticmethod
    def _get_whois_info_from_db(ip_address):
        """
        For getting existing WHOISInfo for given IP from db if present.
        """
        WHOISInfo = load_model("config", "WHOISInfo")

        return WHOISInfo.objects.filter(ip_address=ip_address)

    @staticmethod
    def is_older(dt):
        """
        Check if given datetime is older than the refresh threshold.
        Raises TypeError if datetime is naive (not timezone-aware).
        """
        if not timezone.is_aware(dt):
            raise TypeError("datetime must be timezone-aware")
        return (timezone.now() - dt) >= timedelta(
            days=app_settings.WHOIS_REFRESH_THRESHOLD_DAYS
        )

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
    def check_estimated_location_enabled(org_id):
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
        if not app_settings.WHOIS_CONFIGURED:
            return False
        org_settings = self.get_org_config_settings(org_id=self.device.organization.pk)
        return org_settings.whois_enabled

    @property
    def is_estimated_location_enabled(self):
        """
        Check if the Estimated location feature is enabled.
        """
        if not app_settings.WHOIS_CONFIGURED:
            return False
        org_settings = self.get_org_config_settings(org_id=self.device.organization.pk)
        return org_settings.estimated_location_enabled

    def process_whois_details(self, ip_address):
        """
        Fetch WHOIS details for a given IP address and return only
        the relevant information.
        """
        ip_client = self.get_geoip_client()
        try:
            data = ip_client.city(ip_address=ip_address)
        # Catching all possible exceptions raised by the geoip2 client
        # and raising them with appropriate messages to be handled by the task
        # retry mechanism.
        except (
            errors.AddressNotFoundError,
            errors.AuthenticationError,
            errors.OutOfQueriesError,
            errors.PermissionRequiredError,
        ) as e:
            exc_type = type(e)
            message = EXCEPTION_MESSAGES.get(exc_type)
            if exc_type is errors.AddressNotFoundError:
                message = message.format(ip_address=ip_address)
            raise exc_type(message) from e
        except requests.RequestException:
            raise
        else:
            # The attributes are always present in the response,
            # but they can be None, so added fallbacks.
            address = {
                "city": data.city.name or "",
                "country": data.country.name or "",
                "continent": data.continent.name or "",
                "postal": str(data.postal.code or ""),
            }
            # Coordinates may be None in WHOIS response
            # WHOISInfo.timezone is a non-nullable CharField, so store empty
            # string when missing to avoid IntegrityError on save.
            time_zone, coordinates = "", None
            if location := data.location:
                if location.latitude is not None and location.longitude is not None:
                    coordinates = Point(
                        location.longitude, location.latitude, srid=4326
                    )
                time_zone = location.time_zone or ""
            return {
                "isp": str(data.traits.autonomous_system_organization or ""),
                "asn": str(data.traits.autonomous_system_number or ""),
                "timezone": time_zone,
                "address": address,
                "coordinates": coordinates,
                "cidr": str(data.traits.network or ""),
                "ip_address": ip_address,
            }

    def _need_whois_lookup(self, new_ip):
        """
        This is used to determine if the WHOIS lookup should be triggered
        when the device is saved.

        The lookup is not triggered if:
            - The new IP address is None or it is a private IP address.
            - The WHOIS information of new ip is present and is not older than
              X days (defined by "WHOIS_REFRESH_THRESHOLD_DAYS").
            - WHOIS is disabled in the organization settings. (query from db)
        """
        # Check cheap conditions first before hitting the database
        if not self.is_whois_enabled:
            return False
        if not self.is_valid_public_ip_address(new_ip):
            return False
        whois_obj = self._get_whois_info_from_db(ip_address=new_ip).first()
        if whois_obj and not self.is_older(whois_obj.modified):
            return False
        return True

    def _need_estimated_location_management(self, new_ip):
        """
        Used to determine if Estimated locations need to be created/updated
        or not during WHOIS lookup.
        """
        if not self.is_whois_enabled:
            return False
        if not self.is_valid_public_ip_address(new_ip):
            return False
        if not self.is_estimated_location_enabled:
            return False
        return True

    def trigger_estimated_location_task(self, ip_address):
        """Helper method to trigger the estimated location task."""
        current_app.send_task(
            "whois_estimated_location_task",
            kwargs={"device_pk": self.device.pk, "ip_address": ip_address},
        )

    def get_device_whois_info(self):
        """
        If the WHOIS lookup feature is enabled and the device ``last_ip``
        is a public IP, it fetches WHOIS information for the network device.
        """
        ip_address = self.device.last_ip
        if not (self.is_valid_public_ip_address(ip_address) and self.is_whois_enabled):
            return None
        return self._get_whois_info_from_db(ip_address=ip_address).first()

    def process_ip_data_and_location(self, force_lookup=False):
        """
        Trigger WHOIS lookup based on the conditions of `_need_whois_lookup`
        and also manage estimated locations based on the conditions of
        `_need_estimated_location_management`.
        Tasks are triggered on commit to ensure redundant data is not created.
        """
        new_ip = self.device.last_ip
        initial_ip = self.device._initial_last_ip
        if force_lookup or self._need_whois_lookup(new_ip):
            transaction.on_commit(
                lambda: fetch_whois_details.delay(
                    device_pk=self.device.pk,
                    initial_ip_address=initial_ip,
                )
            )
        # To handle the case when WHOIS already exists as in that case
        # WHOIS lookup is not triggered but we still need to
        # manage estimated locations.
        elif self._need_estimated_location_management(new_ip):
            transaction.on_commit(
                lambda: self.trigger_estimated_location_task(
                    ip_address=new_ip,
                )
            )

    def update_whois_info(self):
        """
        Update existing WHOIS data for the device
        when the data is older than
        ``OPENWISP_CONTROLLER_WHOIS_REFRESH_THRESHOLD_DAYS``.
        """
        ip_address = self.device.last_ip
        if not self.is_valid_public_ip_address(ip_address):
            return
        if not self.is_whois_enabled:
            return
        whois_obj = WHOISService._get_whois_info_from_db(ip_address=ip_address).first()
        if whois_obj and self.is_older(whois_obj.modified):
            transaction.on_commit(
                lambda: fetch_whois_details.delay(
                    device_pk=self.device.pk,
                    initial_ip_address=None,
                )
            )

    def _create_or_update_whois(self, whois_details, whois_instance=None):
        """
        Used to update an existing WHOIS instance; else, creates a new one.
        Returns the updated or created WHOIS instance along with update fields.
        """
        WHOISInfo = load_model("config", "WHOISInfo")
        update_fields = []
        if whois_instance:
            for attr, value in whois_details.items():
                # whois_details already coerce to string most values
                if getattr(whois_instance, attr) != value:
                    update_fields.append(attr)
                    setattr(whois_instance, attr, value)
            # bump modified time so staleness check
            # doesn't re-trigger the lookup
            update_fields.append("modified")
            whois_instance.modified = timezone.now()
            whois_instance.save(update_fields=update_fields)
        else:
            whois_instance = WHOISInfo(**whois_details)
            whois_instance.full_clean()
            whois_instance.save(force_insert=True)
        return whois_instance, update_fields

    def _create_or_update_estimated_location(
        self, location_defaults, attached_devices_exists
    ):
        """
        Create or update estimated location for the device based on the
        given location defaults.
        """
        Location = load_model("geo", "Location")
        DeviceLocation = load_model("geo", "DeviceLocation")

        if not (device_location := getattr(self.device, "devicelocation", None)):
            device_location = DeviceLocation(content_object=self.device)

        current_location = device_location.location

        if not current_location or (
            attached_devices_exists and current_location.is_estimated
        ):
            with transaction.atomic():
                current_location = Location(**location_defaults, is_estimated=True)
                current_location.full_clean()
                current_location.save(_set_estimated=True)
                device_location.location = current_location
                device_location.full_clean()
                device_location.save()
            send_whois_task_notification(
                device=self.device,
                notify_type="estimated_location_created",
                actor=current_location,
            )
        elif current_location.is_estimated:
            update_fields = []
            for attr, value in location_defaults.items():
                if getattr(current_location, attr) != value:
                    setattr(current_location, attr, value)
                    update_fields.append(attr)
            if update_fields:
                with transaction.atomic():
                    current_location.save(
                        update_fields=update_fields, _set_estimated=True
                    )
                send_whois_task_notification(
                    device=self.device,
                    notify_type="estimated_location_updated",
                    actor=current_location,
                )
        return current_location
