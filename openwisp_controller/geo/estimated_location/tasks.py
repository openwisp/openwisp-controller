import logging

from celery import shared_task
from django.db import transaction
from swapper import load_model

from openwisp_controller.config.whois.utils import send_whois_task_notification

logger = logging.getLogger(__name__)


@shared_task
def manage_estimated_locations(device_pk, ip_address):
    """
    Creates/updates estimated location for a device based on the latitude and
    longitude or attaches an existing location.
    Existing location here means a location of another device whose last_ip matches
    the given ip_address.
    Does not alters the existing location if it is not estimated.

    - If the current device has no location or location is estimate, either update
    to an existing location; if it exists, else

    - A new location is created if current device has no location, or
    if it does; it is updated using coords from WHOIS record if it is estimated.

    In case of multiple devices with same last_ip, the task will send a notification
    to the user to resolve the conflict manually.
    """
    Device = load_model("config", "Device")
    Location = load_model("geo", "Location")
    WHOISInfo = load_model("config", "WHOISInfo")
    DeviceLocation = load_model("geo", "DeviceLocation")

    def _create_estimated_location(device_location, location_defaults):
        with transaction.atomic():
            location = Location(**location_defaults, is_estimated=True)
            location.full_clean()
            location.save(_set_estimated=True)
            device_location.location = location
            device_location.full_clean()
            device_location.save()
            logger.info(
                f"Estimated location saved successfully for {device_pk}"
                f" for IP: {ip_address}"
            )
            send_whois_task_notification(
                device_pk=device_pk,
                notify_type="estimated_location_created",
                actor=location,
            )

    def _update_or_create_estimated_location(
        device_location, whois_obj, attached_devices_exists=False
    ):
        # Used to update an existing location if it is estimated
        # or create a new one if it doesn't exist
        if whois_obj and whois_obj.coordinates:
            location_defaults = {
                **whois_obj._get_defaults_for_estimated_location(),
                "organization_id": device.organization_id,
            }
            if current_location and current_location.is_estimated:
                if attached_devices_exists:
                    # If there are other devices attached to the current location,
                    # we do not update it, but create a new one.
                    _create_estimated_location(device_location, location_defaults)
                    return
                update_fields = []
                for attr, value in location_defaults.items():
                    if getattr(current_location, attr) != value:
                        setattr(current_location, attr, value)
                        update_fields.append(attr)
                if update_fields:
                    current_location.save(
                        update_fields=update_fields, _set_estimated=True
                    )
                    logger.info(
                        f"Estimated location saved successfully for {device_pk}"
                        f" for IP: {ip_address}"
                    )
                    send_whois_task_notification(
                        device_pk=device_pk,
                        notify_type="estimated_location_updated",
                        actor=current_location,
                    )
            elif not current_location:
                # If there is no current location, we create a new one.
                _create_estimated_location(device_location, location_defaults)
        else:
            logger.warning(
                f"Coordinates not available for {device_pk} for IP: {ip_address}."
                " Estimated location cannot be determined."
            )
            return

    def _handle_attach_existing_location(
        device, device_location, whois_obj, attached_devices_exists=False
    ):
        # For handling the case when WHOIS already exists for device's new last_ip
        # then we attach the location of the device with same last_ip if it exists.
        devices_with_location = (
            Device.objects.select_related("devicelocation")
            .filter(organization_id=device.organization_id)
            .filter(last_ip=ip_address, devicelocation__location__isnull=False)
            .exclude(pk=device_pk)
        )
        # If there are multiple devices with same last_ip then we need to inform
        # the user to resolve the conflict manually.
        if devices_with_location.count() > 1:
            send_whois_task_notification(
                device_pk=device_pk, notify_type="estimated_location_error"
            )
            logger.error(
                "Multiple devices with locations found with same "
                f"last_ip {ip_address}. Please resolve the conflict manually."
            )
            return
        first_device = devices_with_location.first()
        # If existing devices with same last_ip do not have any location
        # then we create a new location based on WHOIS data.
        if not first_device:
            _update_or_create_estimated_location(
                device_location, whois_obj, attached_devices_exists
            )
            return
        existing_location = first_device.devicelocation.location
        # We need to remove any existing estimated location of the device
        if current_location and not attached_devices_exists:
            current_location.delete()
        device_location.location = existing_location
        device_location.full_clean()
        device_location.save()
        logger.info(
            f"Estimated location saved successfully for {device_pk}"
            f" for IP: {ip_address}"
        )
        send_whois_task_notification(
            device_pk=device_pk,
            notify_type="estimated_location_updated",
            actor=existing_location,
        )

    whois_obj = WHOISInfo.objects.filter(ip_address=ip_address).first()
    device = (
        Device.objects.select_related("devicelocation__location", "organization")
        .only("organization_id", "devicelocation")
        .get(pk=device_pk)
    )

    if not (device_location := getattr(device, "devicelocation", None)):
        device_location = DeviceLocation(content_object=device)

    attached_devices_exists = False
    if current_location := device_location.location:
        attached_devices_exists = (
            Device.objects.filter(devicelocation__location_id=current_location.pk)
            .exclude(pk=device_pk)
            .exists()
        )

    if not current_location or current_location.is_estimated:
        _handle_attach_existing_location(
            device, device_location, whois_obj, attached_devices_exists
        )
    else:
        logger.info(
            f"Non Estimated location already set for {device_pk}. Update"
            f" location manually as per IP: {ip_address}"
        )
