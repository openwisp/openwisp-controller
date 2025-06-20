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
        "No WhoIs information found for IP address {ip_address}"
    ),
    errors.AuthenticationError: _(
        "Authentication failed for GeoIP2 service. "
        "Check your OPENWISP_CONTROLLER_GEOIP_ACCOUNT_ID and "
        "OPENWISP_CONTROLLER_GEOIP_LICENSE_KEY settings."
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
            account_id=app_settings.GEOIP_ACCOUNT_ID,
            license_key=app_settings.GEOIP_LICENSE_KEY,
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
                "Failed to fetch WhoIs details for device"
                " [{notification.target}]({notification.target_link})"
            ),
            description=_(
                f"WhoIs details could not be fetched for ip: {new_ip_address}."
            ),
        )
        logger.error(f"WhoIs lookup failed. Details: {exc}")

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
    def _get_who_is_info_from_db(ip_address):
        """
        For getting existing WhoIsInfo for given IP from db if present.
        """
        WhoIsInfo = load_model("config", "WhoIsInfo")

        return WhoIsInfo.objects.filter(ip_address=ip_address)

    @property
    def is_who_is_enabled(self):
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
                return app_settings.WHO_IS_ENABLED
            cache.set(
                self.get_cache_key(org_id=org_id),
                org_settings,
                timeout=Config._CHECKSUM_CACHE_TIMEOUT,
            )
        return getattr(org_settings, "who_is_enabled", app_settings.WHO_IS_ENABLED)

    def _need_who_is_lookup(self, new_ip):
        """
        This is used to determine if the WhoIs lookup should be triggered
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

        if self._get_who_is_info_from_db(new_ip).exists():
            return False, True

        return self.is_who_is_enabled, False

    def get_device_who_is_info(self):
        """
        Used to get WhoIsInfo for a device if last_ip is valid public ip
        and WhoIs is enabled.
        """
        ip_address = self.device.last_ip
        if not (self.is_valid_public_ip_address(ip_address) and self.is_who_is_enabled):
            return None

        return self._get_who_is_info_from_db(ip_address=ip_address).first()

    def trigger_who_is_lookup(self):
        """
        Trigger WhoIs lookup based on the conditions of `_need_who_is_lookup`.
        Task is triggered on commit to ensure redundant data is not created.
        """

        fetch_who_is, who_is_info_exists = self._need_who_is_lookup(self.device.last_ip)
        if fetch_who_is:
            transaction.on_commit(
                lambda: self.fetch_who_is_details.delay(
                    device_pk=self.device.pk,
                    initial_ip_address=self.device._initial_last_ip,
                    new_ip_address=self.device.last_ip,
                )
            )
        elif who_is_info_exists and self.is_who_is_enabled:
            self.manage_fuzzy_locations.delay(
                self.device.pk, self.device.last_ip, add_existing=True
            )

    # device_pk is used when task fails to report for which device failure occurred
    @shared_task(
        bind=True,
        base=WhoIsCeleryRetryTask,
        **app_settings.API_TASK_RETRY_OPTIONS,
    )
    def fetch_who_is_details(self, device_pk, initial_ip_address, new_ip_address):
        """
        Fetches the WhoIs details of the given IP address
        and creates/updates the WhoIs record.
        """
        # The task can be triggered for same ip address multiple times
        # so we need to return early if WhoIs is already created.
        if WhoIsService._get_who_is_info_from_db(new_ip_address).exists():
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
            # Format address using the data from the geoip2 response
            address = {
                "city": getattr(data.city, "name", ""),
                "country": getattr(data.country, "name", ""),
                "continent": getattr(data.continent, "name", ""),
                "postal": str(getattr(data.postal, "code", "")),
            }
            # create fuzzy location for the device
            location_address = ", ".join(
                i
                for i in (
                    address.get("city"),
                    address.get("country"),
                    address.get("continent"),
                    address.get("postal"),
                )
                if i
            )
            WhoIsService.manage_fuzzy_locations.delay(
                device_pk,
                new_ip_address,
                data.location.latitude,
                data.location.longitude,
                location_address,
            )

            # Create the WhoIs information
            WhoIsInfo.objects.create(
                organization_name=data.traits.autonomous_system_organization,
                asn=data.traits.autonomous_system_number,
                country=data.country.name,
                timezone=data.location.time_zone,
                address=address,
                cidr=data.traits.network,
                ip_address=new_ip_address,
            )
            logger.info(f"Successfully fetched WHOIS details for {new_ip_address}.")

            # the following check ensures that for a case when device last_ip
            # is not changed and there is no related who_is record, we do not
            # delete the newly created record as both `initial_ip_address` and
            # `new_ip_address` would be same for such case.
            if initial_ip_address != new_ip_address:
                # If any active devices are linked to the following record,
                # then they will trigger this task and new record gets created
                # with latest data.
                WhoIsService.delete_who_is_record(ip_address=initial_ip_address)

    @shared_task
    def delete_who_is_record(ip_address):
        """
        Deletes the WhoIs record for the device's last IP address.
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

        # for attaching existing location for the ip to device
        if add_existing and not device_location.location:
            device_with_location = (
                Device.objects.select_related("device_location")
                .filter(last_ip=ip_address, device_location__location__isnull=False)
                .first()
            )
            if device_with_location:
                location = device_with_location.device_location.location
                device_location.location = location
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
