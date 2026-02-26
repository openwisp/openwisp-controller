import logging

from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from geoip2 import errors
from swapper import load_model

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

    def on_success(self, retval, task_id, args, kwargs):
        """Mark the task as successfully completed."""
        task_key = f"{self.name}_last_operation"
        cache.set(task_key, "success", None)
        return super().on_success(retval, task_id, args, kwargs)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Notify the user about the failure of the WHOIS task.

        Notifications are sent only once when task fails for the first time.
        Subsequent failures do not trigger notifications until a successful run occurs.
        """
        device_pk = kwargs.get("device_pk") or (args[0] if args else None)
        if device_pk is not None:
            # All exceptions are treated globally to prevent notification spam.
            # The cache key is global (not per-device) to avoid spamming admins
            # with multiple notifications for the same recurring issue.
            task_key = f"{self.name}_last_operation"
            last_operation = cache.get(task_key)
            if last_operation != "errored":
                cache.set(task_key, "errored", None)
                send_whois_task_notification(
                    device=device_pk, notify_type="whois_device_error"
                )
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

    try:
        device = Device.objects.select_related("devicelocation").get(pk=device_pk)
    except Device.DoesNotExist:
        logger.warning(f"Device {device_pk} not found, skipping WHOIS lookup")
        return
    new_ip_address = device.last_ip
    whois_service = device.whois_service
    # If there is existing WHOIS older record then it needs to be updated
    whois_obj = WHOISInfo.objects.filter(ip_address=new_ip_address).first()
    if whois_obj and not whois_service.is_older(whois_obj.modified):
        return
    # WARNING: execute HTTP requests before transaction lock is acquired
    fetched_details = whois_service.process_whois_details(new_ip_address)

    with transaction.atomic():
        whois_obj, update_fields = whois_service._create_or_update_whois(
            fetched_details, whois_obj
        )
        logger.info(f"Successfully fetched WHOIS details for {new_ip_address}.")
        if initial_ip_address:
            transaction.on_commit(
                # execute synchronously as we're already in a background task
                lambda: delete_whois_record(ip_address=initial_ip_address)
            )
        if not device._get_organization__config_settings().estimated_location_enabled:
            return
        # the estimated location task should not run if old record is updated
        # and location related fields are not updated
        device_location = getattr(device, "devicelocation", None)
        if (
            device_location
            and device_location.location
            and update_fields
            and not any(i in update_fields for i in ["address", "coordinates"])
        ):
            return
        transaction.on_commit(
            lambda: whois_service.trigger_estimated_location_task(
                ip_address=new_ip_address,
            )
        )


@shared_task
def delete_whois_record(ip_address, force=False):
    """
    Deletes the WHOIS record for the device's last IP address.
    This is used when the device is deleted or its last IP address is changed.
    'force' parameter is used to delete the record without checking for linked devices.
    """
    Device = load_model("config", "Device")
    WHOISInfo = load_model("config", "WHOISInfo")
    queryset = WHOISInfo.objects.filter(ip_address=ip_address)
    if force:
        queryset.delete()
    else:
        if (
            not Device.objects.filter(_is_deactivated=False)
            .filter(last_ip=ip_address)
            .exists()
        ):
            queryset.delete()
