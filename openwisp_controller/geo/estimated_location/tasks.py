import logging

from celery import shared_task
from swapper import load_model

from openwisp_controller.config.whois.utils import send_whois_task_notification

logger = logging.getLogger(__name__)


def _handle_attach_existing_location(
    device, device_location, ip_address, existing_device_location
):
    """
    Helper function to:
    1. Attach existing device's location (same last_ip) to current device, else
    2. Update current location of device using WHOIS data; if it exists, else
    3. Create a new estimated location for the device using WHOIS data.
    """
    Device = load_model("config", "Device")
    WHOISInfo = load_model("config", "WHOISInfo")

    current_location = device_location.location
    attached_devices_exists = None
    if current_location is not None:
        attached_devices_exists = (
            Device.objects.filter(devicelocation__location_id=current_location.pk)
            .exclude(pk=device.pk)
            .exists()
        )
    if (
        existing_device_location
        and existing_device_location.location != device_location.location
    ):
        existing_location = existing_device_location.location
        device_location.location = existing_location
        device_location.full_clean()
        device_location.save()
        logger.info(
            f"Estimated location saved successfully for {device.pk}"
            f" for IP: {ip_address}"
        )
        # We need to remove existing estimated location of the device
        # if it is not shared
        if attached_devices_exists is False:
            current_location.delete()
        send_whois_task_notification(
            device=device,
            notify_type="estimated_location_updated",
            actor=existing_location,
        )
        return
    # If existing devices with same last_ip do not have any location
    # then we create a new location based on WHOIS data.
    whois_obj = WHOISInfo.objects.filter(ip_address=ip_address).first()
    if not whois_obj or not whois_obj.coordinates:
        logger.warning(
            f"Coordinates not available for {device.pk} for IP: {ip_address}."
            " Estimated location cannot be determined."
        )
        return

    location_defaults = {
        **whois_obj._get_defaults_for_estimated_location(),
        "organization_id": device.organization_id,
    }
    # Create new location only if location is changed.
    if (
        attached_devices_exists
        and current_location
        and current_location.geometry == location_defaults.get("geometry")
        and current_location.name == location_defaults.get("name")
    ):
        logger.debug(
            f"Estimated location unchanged for {device.pk}"
            f" for IP: {ip_address}, keeping existing location"
        )
        return
    # create new location if no location exists for device or the estimated location
    # of device is shared.
    whois_service = device.whois_service
    whois_service._create_or_update_estimated_location(
        location_defaults, attached_devices_exists
    )
    logger.info(
        f"Estimated location saved successfully for {device.pk}"
        f" for IP: {ip_address}"
    )


@shared_task(name="whois_estimated_location_task")
def manage_estimated_locations(device_pk, ip_address):
    """
    Creates/updates estimated location for a device based on the latitude and
    longitude or attaches an existing location.
    Existing location here means a location of another device whose last_ip matches
    the given ip_address.
    Does not alters the existing location if it is not estimated.

    - If the current device has no location or location is estimated, either update
    to an existing location; if it exists, else

    - A new location is created if current device has no location, or
    if it does; it is updated using coords from WHOIS record if it is estimated.

    In case of multiple devices with same last_ip, the task will send a notification
    to the user to resolve the conflict manually.
    """
    Device = load_model("config", "Device")
    DeviceLocation = load_model("geo", "DeviceLocation")

    try:
        device = Device.objects.select_related("devicelocation__location").get(
            pk=device_pk
        )
    except Device.DoesNotExist:
        logger.warning(
            f"Device {device_pk} not found, skipping manage_estimated_locations"
        )
        return
    devices_with_location = list(
        # "devicelocation" and "devicelocation__location" must be in only() to
        # prevent Django from deferring them, which would conflict with
        # select_related(). Django raises FieldError if a relation field is
        # both deferred and traversed via select_related.
        Device.objects.only(
            "id", "name", "last_ip", "devicelocation", "devicelocation__location"
        )
        .select_related("devicelocation__location")
        .filter(
            organization_id=device.organization_id,
            last_ip=ip_address,
            devicelocation__location__isnull=False,
        )
        # evaluated to LIMIT query, we need to know if there's more than 1 result
        .exclude(pk=device.pk)[:2]
    )
    # multiple devices can have same last_ip in cases like usage of proxy
    if len(devices_with_location) > 1:
        send_whois_task_notification(
            device=device, notify_type="estimated_location_error"
        )
        logger.error(
            "Multiple devices with locations found with same "
            f"last_ip {ip_address}. Please resolve the conflict manually."
        )
        return
    # if device doesn't have a location yet, initialize a draft
    if not (device_location := getattr(device, "devicelocation", None)):
        device_location = DeviceLocation(content_object=device)
    current_location = device_location.location
    if not current_location or current_location.is_estimated:
        # existing device location
        try:
            existing_device_location = getattr(
                devices_with_location[0], "devicelocation", None
            )
        # no existing device location
        except IndexError:
            existing_device_location = None
        _handle_attach_existing_location(
            device, device_location, ip_address, existing_device_location
        )
    else:
        logger.info(
            f"Non Estimated location already set for {device_pk}. Update"
            f" location manually as per IP: {ip_address}"
        )
