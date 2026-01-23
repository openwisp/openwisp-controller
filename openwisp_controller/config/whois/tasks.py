import logging

from celery import shared_task
from django.db import transaction
from geoip2 import errors
from swapper import load_model

from openwisp_controller.geo.estimated_location.tasks import manage_estimated_locations
from openwisp_utils.tasks import OpenwispCeleryTask

from .. import settings as app_settings
from .utils import send_whois_task_notification

logger = logging.getLogger(__name__)


class WHOISCeleryRetryTask(OpenwispCeleryTask):
    """
    Base class for OpenWISP Celery tasks with retry support on failure.
    """

    # this is the exception related to networking errors
    # that should trigger a retry of the task.
    autoretry_for = (errors.HTTPError,)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Notify the user about the failure of the WHOIS task."""
        device_pk = kwargs.get("device_pk")
        send_whois_task_notification(device=device_pk, notify_type="whois_device_error")
        logger.error(f"WHOIS lookup failed. Details: {exc}")
        return super().on_failure(exc, task_id, args, kwargs, einfo)


# device_pk is used when task fails to report for which device failure occurred
@shared_task(
    bind=True,
    base=WHOISCeleryRetryTask,
    **app_settings.API_TASK_RETRY_OPTIONS,
)
def fetch_whois_details(self, device_pk, initial_ip_address):
    """
    Fetches the WHOIS details of the given IP address
    and creates/updates the WHOIS record.
    """
    Device = load_model("config", "Device")
    WHOISInfo = load_model("config", "WHOISInfo")

    with transaction.atomic():
        device = Device.objects.get(pk=device_pk)
        new_ip_address = device.last_ip
        WHOISService = device.whois_service

        # If there is existing WHOIS older record then it needs to be updated
        whois_obj = WHOISInfo.objects.filter(ip_address=new_ip_address).first()
        if whois_obj and not WHOISService.is_older(whois_obj.modified):
            return

        fetched_details = WHOISService.process_whois_details(new_ip_address)
        whois_obj, update_fields = WHOISService._create_or_update_whois(
            fetched_details, whois_obj
        )
        logger.info(f"Successfully fetched WHOIS details for {new_ip_address}.")

        if device._get_organization__config_settings().estimated_location_enabled:
            # the estimated location task should not run if old record is updated
            # and location related fields are not updated
            if update_fields and not any(
                i in update_fields for i in ["address", "coordinates"]
            ):
                return
            manage_estimated_locations.delay(
                device_pk=device_pk, ip_address=new_ip_address
            )

        # delete WHOIS record for initial IP if no devices are linked to it
        if (
            not Device.objects.filter(_is_deactivated=False)
            .filter(last_ip=initial_ip_address)
            .exists()
        ):
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
