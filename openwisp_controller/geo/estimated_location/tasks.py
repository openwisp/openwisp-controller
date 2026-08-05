import logging

from celery import shared_task
from django.db import transaction
from swapper import load_model

from openwisp_controller.config.whois.service import WHOISService
from openwisp_controller.geo.estimated_location.service import EstimatedLocationService

logger = logging.getLogger(__name__)

# Celery tasks validate queued work and coordinate transactions.
# Keep estimated-location decisions in EstimatedLocationService.


@shared_task(name="whois_estimated_location_task")
def manage_estimated_locations(device_pk, ip_address):
    """Update a device's estimated location from its current WHOIS data."""
    Device = load_model("config", "Device")
    WHOISInfo = load_model("config", "WHOISInfo")
    normalize_ip = WHOISService.normalize_ip_address
    ip_address = normalize_ip(ip_address)
    try:
        with transaction.atomic():
            # DeviceLocation and Location are optional, so lock only the Device row.
            # (PostgreSQL cannot lock nullable joined rows).
            device = (
                Device.objects.select_for_update(of=("self",))
                .select_related("organization", "devicelocation__location")
                .get(pk=device_pk)
            )
            if (
                device.is_deactivated()
                or not device.organization.is_active
                or normalize_ip(device.last_ip) != ip_address
            ):
                logger.info(
                    f"Device {device_pk} no longer needs estimated location "
                    f"for {ip_address}"
                )
                return
            if not EstimatedLocationService.check_estimated_location_enabled(
                device.organization_id
            ):
                return
            whois_obj = WHOISInfo.objects.filter(ip_address=ip_address).first()
            EstimatedLocationService(device).update_from_whois(ip_address, whois_obj)
    except Device.DoesNotExist:
        logger.warning(
            f"Device {device_pk} not found, skipping manage_estimated_locations"
        )
