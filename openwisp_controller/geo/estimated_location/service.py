import logging

from celery import current_app
from django.core.cache import cache
from django.db import transaction
from swapper import load_model

from openwisp_controller.config import settings as config_app_settings

from .utils import (
    get_location_defaults_from_whois,
    send_estimated_location_notification,
)

logger = logging.getLogger(__name__)


class EstimatedLocationService:
    def __init__(self, device):
        self.device = device

    @staticmethod
    def check_estimated_location_enabled(org_id):
        """
        Return whether estimated location is enabled for the given organization.

        OrganizationGeoSettings are cached to avoid a DB hit on every check.
        If no settings exist for the organization, an empty instance is used so
        that the FallbackBooleanChoiceField can provide the global default.
        """
        if not org_id:
            return False
        if not config_app_settings.WHOIS_CONFIGURED:
            return False

        OrganizationGeoSettings = load_model("geo", "OrganizationGeoSettings")
        cache_key = EstimatedLocationService.get_cache_key(org_id)
        org_settings = cache.get(cache_key)
        if org_settings is None:
            try:
                org_settings = OrganizationGeoSettings.objects.get(
                    organization_id=org_id
                )
            except OrganizationGeoSettings.DoesNotExist:
                # Cache a sentinel object (empty settings instance) so subsequent
                # calls do not hit the database repeatedly.
                org_settings = OrganizationGeoSettings(organization_id=org_id)
            cache.set(cache_key, org_settings, timeout=24 * 7 * 3600)
        return org_settings.estimated_location_enabled

    @staticmethod
    def get_cache_key(org_id):
        """Return cache key used for caching OrganizationGeoSettings."""
        return f"organization_geo_{org_id}"

    @classmethod
    def invalidate_org_settings_cache(cls, instance, **kwargs):
        """
        Invalidate the cache for Organization geo settings on update/delete of
        OrganizationGeoSettings instance.
        """
        cache.delete(cls.get_cache_key(instance.organization_id))

    @property
    def is_estimated_location_enabled(self):
        return self.check_estimated_location_enabled(self.device.organization_id)

    def trigger_estimated_location_task(self, ip_address):
        # Do not re-derive estimated location for deactivated devices.
        if self.device.is_deactivated():
            return

        def _send():
            try:
                current_app.send_task(
                    "whois_estimated_location_task",
                    kwargs={"device_pk": self.device.pk, "ip_address": ip_address},
                )
            except Exception as e:
                logger.error(
                    "Failed to enqueue estimated location task for device %s ip %s: %s",
                    self.device.pk,
                    ip_address,
                    e,
                )

        transaction.on_commit(_send)

    def update_from_whois(self, ip_address, whois):
        """Create, update, or share an estimated location from WHOIS data."""
        Device = load_model("config", "Device")
        DeviceLocation = load_model("geo", "DeviceLocation")
        devices_with_location = list(
            Device.objects.only("id", "devicelocation", "devicelocation__location")
            .select_related("devicelocation__location")
            .filter(
                organization_id=self.device.organization_id,
                _is_deactivated=False,
                last_ip=ip_address,
                devicelocation__location__isnull=False,
            )
            .exclude(pk=self.device.pk)[:2]
        )
        location_ids = {
            device.devicelocation.location_id for device in devices_with_location
        }
        if len(location_ids) > 1:
            send_estimated_location_notification(
                device=self.device, notify_type="estimated_location_error"
            )
            logger.error(
                "Multiple devices with locations found with same "
                f"last_ip {ip_address}. Please resolve the conflict manually."
            )
            return
        if not (device_location := getattr(self.device, "devicelocation", None)):
            device_location = DeviceLocation(content_object=self.device)
        current_location = device_location.location
        if not current_location or current_location.is_estimated:
            existing_device_location = None
            if devices_with_location:
                existing_device_location = devices_with_location[0].devicelocation
            self._handle_attach_existing_location(
                device_location, ip_address, existing_device_location, whois
            )
        else:
            logger.info(
                f"Non Estimated location already set for {self.device.pk}. Update"
                f" location manually as per IP: {ip_address}"
            )

    def _handle_attach_existing_location(
        self, device_location, ip_address, existing_device_location, whois
    ):
        """Attach a shared location or create or update an estimated location."""
        Device = load_model("config", "Device")
        current_location = device_location.location
        attached_devices_exists = None
        if current_location is not None:
            attached_devices_exists = (
                Device.objects.filter(devicelocation__location_id=current_location.pk)
                .exclude(pk=self.device.pk)
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
                f"Estimated location saved successfully for {self.device.pk}"
                f" for IP: {ip_address}"
            )
            # Delete the previous estimated location only when this device did
            # not share it.
            if attached_devices_exists is False:
                current_location.delete()
            send_estimated_location_notification(
                device=self.device,
                notify_type="estimated_location_updated",
                actor=existing_location,
                ip_address=ip_address,
                whois=whois,
            )
            return
        # No peer location is available, so derive an estimated location from WHOIS.
        if not whois or not whois.coordinates:
            logger.warning(
                f"Coordinates not available for {self.device.pk} for IP: {ip_address}."
                " Estimated location cannot be determined."
            )
            return
        location_defaults = {
            **get_location_defaults_from_whois(whois),
            "organization_id": self.device.organization_id,
        }
        # Do not replace a shared estimated location with equivalent WHOIS data.
        if (
            attached_devices_exists
            and current_location
            and current_location.geometry == location_defaults.get("geometry")
            and current_location.name == location_defaults.get("name")
        ):
            logger.debug(
                f"Estimated location unchanged for {self.device.pk}"
                f" for IP: {ip_address}, keeping existing location"
            )
            return
        self._create_or_update_estimated_location(
            device_location, location_defaults, attached_devices_exists, whois
        )
        logger.info(
            f"Estimated location saved successfully for {self.device.pk}"
            f" for IP: {ip_address}"
        )

    def _create_or_update_estimated_location(
        self, device_location, location_defaults, attached_devices_exists, whois
    ):
        """
        Create or update estimated location for the device based on the
        given location defaults.
        """
        Location = load_model("geo", "Location")
        current_location = device_location.location
        # Re-check whether estimated locations are enabled for the device's
        # organization. The check is needed here so the celery worker
        # honors current org settings and avoids persisting estimated
        # locations when the feature has been disabled since the task was
        # enqueued.
        if not self.check_estimated_location_enabled(self.device.organization_id):
            return current_location
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

                send_estimated_location_notification(
                    device=self.device,
                    notify_type="estimated_location_created",
                    actor=current_location,
                    ip_address=whois.ip_address,
                    whois=whois,
                )
        elif current_location.is_estimated:
            update_fields = []
            for attr, value in location_defaults.items():
                if getattr(current_location, attr) != value:
                    setattr(current_location, attr, value)
                    update_fields.append(attr)
            if update_fields:
                current_location.full_clean()
                with transaction.atomic():
                    current_location.save(
                        update_fields=update_fields, _set_estimated=True
                    )
                send_estimated_location_notification(
                    device=self.device,
                    notify_type="estimated_location_updated",
                    actor=current_location,
                    ip_address=whois.ip_address,
                    whois=whois,
                )
        return current_location
