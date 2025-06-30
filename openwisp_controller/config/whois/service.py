import logging
from ipaddress import ip_address

import requests
from celery import shared_task
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.db import transaction
from django.utils.translation import gettext as _
from geoip2 import errors
from geoip2 import webservice as geoip2_webservice
from openwisp_notifications.signals import notify
from swapper import load_model

from openwisp_controller.config import settings as app_settings
from openwisp_utils.tasks import OpenwispCeleryTask

logger = logging.getLogger(__name__)


EXCEPTION_MESSAGES = {
    errors.AddressNotFoundError: _(
        "No WHOIS information found for IP address {ip_address}"
    ),
    errors.AuthenticationError: _(
        "Authentication failed for GeoIP2 service. "
        "Check your OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT and "
        "OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY settings."
    ),
    errors.OutOfQueriesError: _(
        "Your account has run out of queries for the GeoIP2 service."
    ),
    errors.PermissionRequiredError: _(
        "Your account does not have permission to access this service."
    ),
}


class WhoIsCeleryRetryTask(OpenwispCeleryTask):
    """
    Base class for OpenWISP Celery tasks with retry support on failure.
    """

    # this is the exception related to networking errors
    # that should trigger a retry of the task.
    autoretry_for = (errors.HTTPError,)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        WhoIsService.notify_on_failure_static(kwargs, exc)
        return super().on_failure(exc, task_id, args, kwargs, einfo)


class WhoIsService:
    """
    A handler class for managing the WhoIs functionality.
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
    def _get_geoip2_client():
        """
        Initializes a geoip2 webservice client instance.
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
    def notify_on_failure_static(kwargs, exc):
        """
        Notify the user about the failure of the WhoIs task.
        This is a static method to avoid circular imports.
        """
        Device = load_model("config", "Device")

        device_pk = kwargs.get("device_pk")
        new_ip_address = kwargs.get("new_ip_address")
        device = Device.objects.get(pk=device_pk)

        notify.send(
            sender=device,
            type="generic_message",
            target=device,
            action_object=device,
            level="error",
            message=_(
                "Failed to fetch WHOIS details for device"
                " [{notification.target}]({notification.target_link})"
            ),
            description=_(
                f"WHOIS details could not be fetched for ip: {new_ip_address}."
            ),
        )
        logger.error(f"WHOIS lookup failed. Details: {exc}")

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
        For getting existing WhoIsInfo for given IP from db if present.
        """
        WhoIsInfo = load_model("config", "WhoIsInfo")

        return WhoIsInfo.objects.filter(ip_address=ip_address)

    @property
    def is_whois_enabled(self):
        """
        Check if WhoIs is enabled for the organization of the device.
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
            - The WhoIs information of new ip is already present.
            - WhoIs is disabled in the organization settings. (query from db)

        Two boolean values are returned:
            - First boolean indicates if WhoIs lookup is needed.
            - Second boolean indicates if WhoIs info already exists in the db,
            which is used for managing fuzzy locations.
        """

        # Check cheap conditions first before hitting the database
        if not self.is_valid_public_ip_address(new_ip):
            return False, False

        if self._get_whois_info_from_db(new_ip).exists():
            return False, True

        return self.is_whois_enabled, False

    def get_device_whois_info(self):
        """
        Used to get WhoIsInfo for a device if last_ip is valid public ip
        and WhoIs is enabled.
        """
        ip_address = self.device.last_ip
        if not (self.is_valid_public_ip_address(ip_address) and self.is_whois_enabled):
            return None

        return self._get_whois_info_from_db(ip_address=ip_address).first()

    def trigger_whois_lookup(self):
        """
        Trigger WhoIs lookup based on the conditions of `_need_whois_lookup`.
        Task is triggered on commit to ensure redundant data is not created.
        """

        fetch_whois, whois_info_exists = self._need_whois_lookup(self.device.last_ip)
        if fetch_whois:
            transaction.on_commit(
                lambda: self.fetch_whois_details.delay(
                    device_pk=self.device.pk,
                    initial_ip_address=self.device._initial_last_ip,
                    new_ip_address=self.device.last_ip,
                )
            )
        elif whois_info_exists and self.is_whois_enabled:
            self.manage_fuzzy_locations.delay(
                self.device.pk, self.device.last_ip, add_existing=True
            )

    # device_pk is used when task fails to report for which device failure occurred
    @shared_task(
        bind=True,
        base=WhoIsCeleryRetryTask,
        **app_settings.API_TASK_RETRY_OPTIONS,
    )
    def fetch_whois_details(self, device_pk, initial_ip_address, new_ip_address):
        """
        Fetches the WhoIs details of the given IP address
        and creates/updates the WhoIs record.
        """
        # The task can be triggered for same ip address multiple times
        # so we need to return early if WhoIs is already created.
        if WhoIsService._get_whois_info_from_db(new_ip_address).exists():
            return

        WhoIsInfo = load_model("config", "WhoIsInfo")

        ip_client = WhoIsService._get_geoip2_client()

        try:
            data = ip_client.city(ip_address=new_ip_address)

        # Catching all possible exceptions raised by the geoip2 client
        # logging the exceptions and raising them with appropriate messages
        except (
            errors.AddressNotFoundError,
            errors.AuthenticationError,
            errors.OutOfQueriesError,
            errors.PermissionRequiredError,
        ) as e:
            exc_type = type(e)
            message = EXCEPTION_MESSAGES.get(exc_type)
            if exc_type is errors.AddressNotFoundError:
                message = message.format(ip_address=new_ip_address)
            raise exc_type(message)
        except requests.RequestException as e:
            raise e

        else:
            # The attributes are always present in the response,
            # but they can be None, so added fallbacks.
            address = {
                "city": data.city.name or "",
                "country": data.country.name or "",
                "continent": data.continent.name or "",
                "postal": str(data.postal.code or ""),
            }

            whois_obj = WhoIsInfo(
                isp=data.traits.autonomous_system_organization,
                asn=data.traits.autonomous_system_number,
                timezone=data.location.time_zone,
                address=address,
                cidr=data.traits.network,
                ip_address=new_ip_address,
            )
            whois_obj.full_clean()
            whois_obj.save()
            logger.info(f"Successfully fetched WHOIS details for {new_ip_address}.")
            location_address = whois_obj.formatted_address

            WhoIsService.manage_fuzzy_locations.delay(
                device_pk,
                new_ip_address,
                data.location.latitude,
                data.location.longitude,
                location_address,
            )

            # the following check ensures that for a case when device last_ip
            # is not changed and there is no related WHOIS record, we do not
            # delete the newly created record as both `initial_ip_address` and
            # `new_ip_address` would be same for such case.
            if initial_ip_address != new_ip_address:
                # If any active devices are linked to the following record,
                # then they will trigger this task and new record gets created
                # with latest data.
                WhoIsService.delete_whois_record(ip_address=initial_ip_address)

    @shared_task
    def delete_whois_record(ip_address):
        """
        Deletes the WHOIS record for the device's last IP address.
        This is used when the device is deleted or its last IP address is changed.
        """
        WhoIsInfo = load_model("config", "WhoIsInfo")

        queryset = WhoIsInfo.objects.filter(ip_address=ip_address)
        if queryset.exists():
            queryset.delete()

    @shared_task
    def manage_fuzzy_locations(
        device_pk,
        ip_address,
        latitude=None,
        longitude=None,
        address=None,
        add_existing=False,
    ):
        """
        Creates/updates fuzzy location for a device based on the latitude and longitude
        or attaches an existing location if `add_existing` is True.
        Existing location here means a location of another device whose last_ip matches
        the given ip_address.

        - If attaching existing location and current device has no location then the existing
        location is attached to the current device as well.
        - If attaching existing location and current device already has a location,
        then current device's location is deleted and set same as existing device's location.
        - If not attaching existing then new location is created if no location exists for
        current device, or existing one is updated if it is fuzzy.
        """
        Device = load_model("config", "Device")
        Location = load_model("geo", "Location")
        DeviceLocation = load_model("geo", "DeviceLocation")

        device_location = (
            DeviceLocation.objects.filter(content_object_id=device_pk)
            .select_related("location")
            .first()
        )

        if not device_location:
            device_location = DeviceLocation(content_object_id=device_pk)

        # if attaching an existing location, the current device should not have
        # a location already set.
        current_location = device_location.location
        if add_existing and (not current_location or current_location.fuzzy):
            existing_device_location = (
                Device.objects.select_related("devicelocation")
                .filter(last_ip=ip_address, devicelocation__location__isnull=False)
                .exclude(pk=device_pk)
                .first()
            )
            if existing_device_location:
                existing_location = existing_device_location.devicelocation.location
                if current_location and current_location.pk != existing_location.pk:
                    # If current device already has a location, delete it
                    # and set the existing location.
                    current_location.delete()

                device_location.location = existing_location
                device_location.full_clean()
                device_location.save()
        elif latitude and longitude:
            device = Device.objects.get(pk=device_pk)
            coords = Point(longitude, latitude, srid=4326)
            # Create/update the device location mapping, updating existing location
            # if exists else create a new location
            location_defaults = {
                "name": f"{device.name} Location",
                "type": "outdoor",
                "organization_id": device.organization_id,
                "is_mobile": False,
                "geometry": coords,
                "address": address,
            }
            if device_location.location and device_location.location.fuzzy:
                for attr, value in location_defaults.items():
                    setattr(device_location.location, attr, value)
                device_location.location.full_clean()
                device_location.location.save()
            elif not device_location.location:
                location = Location(**location_defaults, fuzzy=True)
                location.full_clean()
                location.save()
                device_location.location = location
                device_location.full_clean()
                device_location.save()
