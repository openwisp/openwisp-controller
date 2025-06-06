import logging
from functools import cached_property
from ipaddress import ip_address

import requests
from celery import shared_task
from django.db import transaction
from django.db.models import Subquery
from django.utils.translation import gettext as _
from geoip2 import errors
from geoip2 import webservice as geoip2_webservice
from openwisp_notifications.signals import notify
from swapper import load_model

from openwisp_controller.config import settings as app_settings
from openwisp_utils.tasks import OpenwispCeleryTask

logger = logging.getLogger(__name__)

OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")
Device = load_model("config", "Device")
WhoIsInfo = load_model("config", "WhoIsInfo")

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
    def _get_geoip2_client():
        """
        Returns a geoip2 webservice client instance.
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
                f"WhoIs details could not be fetched for ip: {new_ip_address}.\n"
                f"Details: {exc}"
            ),
        )
        logger.error(f"WhoIs lookup failed for : {device_pk} for IP: {new_ip_address}.")

    @staticmethod
    def is_valid_public_ip_address(ip):
        """
        Returns True if the given IP address is a valid public IP address.
        """
        try:
            return ip and ip_address(ip).is_global
        except ValueError:
            return False

    @cached_property
    def is_whois_enabled(self):
        """
        Returns True if WhoIs is enabled for the organization of the device.
        """
        try:
            device_pk = self.device.pk
            # here we are fetching the organization settings from db instead of through
            # device as in some views like `DeviceChecksumView` the device instance is
            # cached, leading to stale data. Have used Subquery to fetch the settings
            # in a single query.
            org_settings = OrganizationConfigSettings.objects.get(
                organization=Subquery(
                    Device.objects.filter(pk=device_pk).values("organization_id")[:1]
                )
            )
            return getattr(org_settings, "whois_enabled", app_settings.WHOIS_ENABLED)
        except OrganizationConfigSettings.DoesNotExist:
            # If organization settings do not exist, fall back to global setting
            return app_settings.WHOIS_ENABLED

    def _get_existing_whois(self, ip_address):
        """
        Returns existing WhoIsInfo for given IP if present.
        """
        return WhoIsInfo.objects.filter(ip_address=ip_address).first()

    def _need_whois_lookup(self, initial_ip, new_ip):
        """
        Returns True if the WhoIs lookup is needed.
        This is used to determine if the WhoIs lookup should be triggered
        when the device is saved.

        The lookup is triggered if:
            - The new IP address is not None.
            - The WhoIs information is not already present or the initial IP is
              different from the new IP.
            - The new IP address is a global (public) IP address.
            - WhoIs is enabled in the organization settings. (query from db)
        """

        # Check cheap conditions first before hitting the database
        return (
            self.is_valid_public_ip_address(new_ip)
            and (initial_ip != new_ip or not self._get_existing_whois(new_ip))
            and self.is_whois_enabled
        )

    def get_whois_info(self):
        """
        Returns WhoIsInfo for the device if IP is valid public ip and WhoIs is enabled.
        """
        ip_address = self.device.last_ip
        if not (self.is_valid_public_ip_address(ip_address) and self.is_whois_enabled):
            return None

        return self._get_existing_whois(ip_address=ip_address)

    def trigger_whois_lookup(self):
        """
        Trigger WhoIs lookup based on the conditions of `_need_whois_lookup`.
        Task is triggered on commit to ensure redundant data is not created.
        """
        if self._need_whois_lookup(self.device._initial_last_ip, self.device.last_ip):
            transaction.on_commit(
                lambda: self.fetch_whois_details.delay(
                    device_pk=self.device.pk,
                    initial_ip_address=self.device._initial_last_ip,
                    new_ip_address=self.device.last_ip,
                )
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
        WhoIsInfo = load_model("config", "WhoIsInfo")

        try:
            ip_client = WhoIsService._get_geoip2_client()

            data = ip_client.city(ip_address=new_ip_address)
            # Format address using the data from the geoip2 response
            address = {
                "city": getattr(data.city, "name", ""),
                "country": getattr(data.country, "name", ""),
                "continent": getattr(data.continent, "name", ""),
                "postal": str(getattr(data.postal, "code", "")),
            }
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
            # is not changed and there is no related whois record, we do not
            # delete the newly created record as both `initial_ip_address` and
            # `new_ip_address` would be same for such case.
            if initial_ip_address != new_ip_address:
                # If any active devices are linked to the following record,
                # then they will trigger this task and new record gets created
                # with latest data.
                WhoIsService.delete_whois_record(ip_address=initial_ip_address)

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
            logger.error(message)
            raise exc_type(message)
        except requests.RequestException as e:
            logger.error(f"Error fetching WHOIS details for {new_ip_address}: {e}")
            raise e

    @shared_task
    def delete_whois_record(ip_address):
        """
        Deletes the WhoIs record for the device's last IP address.
        This is used when the device is deleted or its last IP address is changed.
        """
        WhoIsInfo = load_model("config", "WhoIsInfo")

        queryset = WhoIsInfo.objects.filter(ip_address=ip_address)
        if queryset.exists():
            queryset.delete()
