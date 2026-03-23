import logging

from django.conf import settings
from django.db import transaction
from swapper import load_model

from openwisp_controller.config import settings as config_app_settings

logger = logging.getLogger(__name__)


class EstimatedLocationService:
    def __init__(self, device):
        self.device = device

    @staticmethod
    def check_estimated_location_enabled(org_id):
        if not org_id:
            return False
        if not config_app_settings.WHOIS_CONFIGURED:
            return False
        OrganizationGeoSettings = load_model("geo", "OrganizationGeoSettings")
        try:
            org_settings = OrganizationGeoSettings.objects.get(organization_id=org_id)
        except OrganizationGeoSettings.DoesNotExist:
            from .. import settings as geo_app_settings

            return geo_app_settings.ESTIMATED_LOCATION_ENABLED
        return org_settings.estimated_location_enabled

    @property
    def is_estimated_location_enabled(self):
        if not config_app_settings.WHOIS_CONFIGURED:
            return False
        return self.check_estimated_location_enabled(self.device.organization_id)

    def trigger_estimated_location_task(self, ip_address):
        current_app = settings.CELERY_APP
        current_app.send_task(
            "whois_estimated_location_task",
            kwargs={"device_pk": self.device.pk, "ip_address": ip_address},
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
            from openwisp_controller.config.whois.utils import (
                send_whois_task_notification,
            )

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
                with transaction.atomic():
                    current_location.save(
                        update_fields=update_fields, _set_estimated=True
                    )
                from openwisp_controller.config.whois.utils import (
                    send_whois_task_notification,
                )

                send_whois_task_notification(
                    device=self.device,
                    notify_type="estimated_location_updated",
                    actor=current_location,
                )
        return current_location
