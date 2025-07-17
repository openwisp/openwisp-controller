import logging

from celery import shared_task
from django.contrib.gis.geos import Point
from swapper import load_model

logger = logging.getLogger(__name__)


@shared_task
def manage_estimated_locations(device_pk, ip_address, add_existing=False):
    """
    Creates/updates estimated location for a device based on the latitude and
    longitude or attaches an existing location if `add_existing` is True.
    Existing location here means a location of another device whose last_ip matches
    the given ip_address.

    When `add_existing` is True:
    - If the current device has no location, attach the existing one; if it does,
    update it with the existing one only if it is estimated (fuzzy).

    When `add_existing` is False:
    - A new location is created if no location exists for current device, or
    existing one is updated using coords from WHOIS record if it is estimated (fuzzy).
    """
    from openwisp_controller.config.whois.utils import send_whois_task_notification

    Device = load_model("config", "Device")
    Location = load_model("geo", "Location")
    WHOISInfo = load_model("config", "WHOISInfo")
    DeviceLocation = load_model("geo", "DeviceLocation")

    device = Device.objects.get(pk=device_pk)
    whois_obj = WHOISInfo.objects.filter(ip_address=ip_address).first()
    device_location, _ = DeviceLocation.objects.select_related(
        "location"
    ).get_or_create(content_object_id=device_pk)
    current_location = device_location.location

    def _create_update_location():
        coords = Point(whois_obj.longitude, whois_obj.latitude, srid=4326)
        address = whois_obj.formatted_address
        location_name = (
            ",".join(address.split(",")[:2]) + f" (Estimated Location: {ip_address})"
            if address
            else f"Estimated Location: {ip_address}"
        )
        # Used to update an existing location if it is estimated
        # or create a new one if it doesn't exist
        location_defaults = {
            "name": location_name,
            "type": "outdoor",
            "organization_id": device.organization_id,
            "is_mobile": False,
            "geometry": coords,
            "address": address,
        }
        if current_location and current_location.is_estimated:
            for attr, value in location_defaults.items():
                setattr(current_location, attr, value)
            current_location.full_clean()
            current_location.save()
        elif not current_location:
            location = Location(**location_defaults, is_estimated=True)
            location.full_clean()
            location.save()
            device_location.location = location
            device_location.full_clean()
            device_location.save()

    # For handling the case when WHOIS already exists for device's new last_ip
    # then we attach the location of the device with same last_ip if it exists.
    if add_existing and (not current_location or current_location.is_estimated):
        existing_devices_location = (
            Device.objects.select_related("devicelocation")
            .filter(organization_id=device.organization_id)
            .filter(last_ip=ip_address, devicelocation__location__isnull=False)
            .exclude(pk=device_pk)
        )
        # If there are multiple devices with same last_ip then we need to inform
        # the user to resolve the conflict manually.
        if existing_devices_location.count() > 1:
            send_whois_task_notification(
                device_pk=device_pk, notify_type="location_error"
            )
            return
        # If existing devices with same last_ip do not have any location
        # then we create a new location based on WHOIS data.
        if existing_devices_location.count() == 0:
            _create_update_location()
            return
        existing_location = existing_devices_location.first().devicelocation.location
        # We need to remove any existing estimated location of the device
        if current_location and current_location.pk != existing_location.pk:
            current_location.delete()
        device_location.location = existing_location
        device_location.full_clean()
        device_location.save()
    elif whois_obj and whois_obj.latitude and whois_obj.longitude:
        _create_update_location()

    logger.info(
        f"Estimated location saved successfully for {device_pk} for IP: {ip_address}"
    )
