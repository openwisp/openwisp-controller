import logging

from celery import current_app
from django.core.cache import cache
from django.db import transaction
from swapper import load_model

from openwisp_controller.config import settings as config_app_settings
from openwisp_controller.config.whois.utils import send_whois_task_notification

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
        try:
            current_app.send_task(
                "whois_estimated_location_task",
                kwargs={"device_pk": self.device.pk, "ip_address": ip_address},
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Failed to enqueue estimated location task for device %s ip %s: %s",
                getattr(self.device, "pk", None),
                ip_address,
                exc,
            )

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
                current_location.full_clean()
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
