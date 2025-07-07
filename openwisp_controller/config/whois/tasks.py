import logging

import requests
from celery import shared_task
from django.contrib.gis.geos import Point
from django.utils.translation import gettext as _
from geoip2 import errors
from geoip2 import webservice as geoip2_webservice
from openwisp_notifications.signals import notify
from swapper import load_model

from openwisp_utils.tasks import OpenwispCeleryTask

from .. import settings as app_settings

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


class WHOISCeleryRetryTask(OpenwispCeleryTask):
    """
    Base class for OpenWISP Celery tasks with retry support on failure.
    """

    # this is the exception related to networking errors
    # that should trigger a retry of the task.
    autoretry_for = (errors.HTTPError,)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Notify the user about the failure of the WHOIS task."""
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
        return super().on_failure(exc, task_id, args, kwargs, einfo)


# device_pk is used when task fails to report for which device failure occurred
@shared_task(
    bind=True,
    base=WHOISCeleryRetryTask,
    **app_settings.API_TASK_RETRY_OPTIONS,
)
def fetch_whois_details(self, device_pk, initial_ip_address, new_ip_address):
    """
    Fetches the WHOIS details of the given IP address
    and creates/updates the WHOIS record.
    """
    WHOISInfo = load_model("config", "WHOISInfo")

    # The task can be triggered for same ip address multiple times
    # so we need to return early if WHOIS is already created.
    if WHOISInfo.objects.filter(ip_address=new_ip_address).exists():
        return

    # Host is based on the db that is used to fetch the details.
    # As we are using GeoLite2, 'geolite.info' host is used.
    # Refer: https://geoip2.readthedocs.io/en/latest/#sync-web-service-example
    ip_client = geoip2_webservice.Client(
        account_id=app_settings.WHOIS_GEOIP_ACCOUNT,
        license_key=app_settings.WHOIS_GEOIP_KEY,
        host="geolite.info",
    )

    try:
        data = ip_client.city(ip_address=new_ip_address)

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

        whois_obj = WHOISInfo(
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
        manage_fuzzy_locations.delay(
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
            delete_whois_record(ip_address=initial_ip_address)


@shared_task
def delete_whois_record(ip_address):
    """
    Deletes the WHOIS record for the device's last IP address.
    This is used when the device is deleted or its last IP address is changed.
    """
    WHOISInfo = load_model("config", "WHOISInfo")

    queryset = WHOISInfo.objects.filter(ip_address=ip_address)
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

    - If attaching existing location and current device has no location then the
    existing location is attached to the current device as well.
    - If attaching existing location and current device already has location, then
    current device's location is deleted and set same as existing device's location.
    - If not attaching existing then new location is created if no location exists for
    current device, or existing one is updated if it is approximate(fuzzy).
    """
    Device = load_model("config", "Device")
    Location = load_model("geo", "Location")
    DeviceLocation = load_model("geo", "DeviceLocation")

    device = Device.objects.get(pk=device_pk)

    device_location, _ = DeviceLocation.objects.select_related(
        "location"
    ).get_or_create(content_object_id=device_pk)

    current_location = device_location.location
    # For handling the case when WHOIS already exists for device's new last_ip
    # then we attach the location of the device with same last_ip if it exists.
    if add_existing and (not current_location or current_location.is_approximate):
        existing_device_location = (
            Device.objects.select_related("devicelocation")
            .filter(organization_id=device.organization_id)
            .filter(last_ip=ip_address, devicelocation__location__isnull=False)
            .exclude(pk=device_pk)
            .first()
        )
        if existing_device_location:
            existing_location = existing_device_location.devicelocation.location
            # We need to remove any existing approximate location of the device
            if current_location and current_location.pk != existing_location.pk:
                current_location.delete()
            device_location.location = existing_location
            device_location.full_clean()
            device_location.save()
    elif latitude and longitude:
        coords = Point(longitude, latitude, srid=4326)
        location_name = (
            " ".join(address.split(",")[:2])
            if address
            else f"Approximate Location {ip_address}"
        )
        # Used to update an existing location if it is approximate
        # or create a new one if it doesn't exist
        location_defaults = {
            "name": location_name,
            "type": "outdoor",
            "organization_id": device.organization_id,
            "is_mobile": False,
            "geometry": coords,
            "address": address,
        }
        if current_location and current_location.is_approximate:
            for attr, value in location_defaults.items():
                setattr(current_location, attr, value)
            current_location.full_clean()
            current_location.save()
        elif not current_location:
            location = Location(**location_defaults, is_approximate=True)
            location.full_clean()
            location.save()
            device_location.location = location
            device_location.full_clean()
            device_location.save()
    logger.info(
        f"Fuzzy location saved successfully for {device_pk} for IP: {ip_address}"
    )
