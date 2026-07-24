import logging
from datetime import timedelta

from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone
from geoip2 import errors
from swapper import load_model

from openwisp_controller.config.signals import whois_fetched
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
def fetch_whois_details(self, device_pk, ip_address):
    """
    Fetches the WHOIS details of the given IP address
    and creates/updates the WHOIS record.
    """
    Device = load_model("config", "Device")
    WHOISInfo = load_model("config", "WHOISInfo")
    normalize_ip = WHOISService.normalize_ip_address
    device = Device.objects.filter(pk=device_pk).first()
    if not device:
        logger.warning(f"Device {device_pk} not found, skipping WHOIS lookup")
        return
    whois_service = device.whois_service
    ip_address = normalize_ip(ip_address)
    if (
        device.is_deactivated()
        or normalize_ip(device.last_ip) != ip_address
        or not whois_service.is_valid_public_ip_address(ip_address)
        or not whois_service.is_whois_enabled
    ):
        logger.info(f"Device {device_pk} no longer needs WHOIS lookup for {ip_address}")
        return
    # If there is existing WHOIS older record then it needs to be updated
    whois_obj = WHOISInfo.objects.filter(ip_address=ip_address).first()
    if whois_obj and not whois_service.is_older(whois_obj.modified):
        return
    # WARNING: execute HTTP requests before transaction lock is acquired
    fetched_details = whois_service.process_whois_details(ip_address)

    with transaction.atomic():
        device = Device.objects.select_for_update().filter(pk=device_pk).first()
        if (
            not device
            or device.is_deactivated()
            or normalize_ip(device.last_ip) != ip_address
            or not device.whois_service.is_whois_enabled
        ):
            return
        whois_obj = (
            WHOISInfo.objects.select_for_update().filter(ip_address=ip_address).first()
        )
        whois_obj, update_fields = whois_service._create_or_update_whois(
            fetched_details, whois_obj
        )
        WHOISInfo.objects.filter(pk=whois_obj.pk).update(unreferenced_since=None)
        logger.info(f"Successfully fetched WHOIS details for {ip_address}.")
        transaction.on_commit(
            lambda: whois_fetched.send(
                sender=WHOISInfo,
                whois=whois_obj,
                updated_fields=update_fields,
                device=device,
            )
        )


@shared_task
def cleanup_unreferenced_whois_records():
    """Delete expired WHOIS cache records that have no active device reference."""
    Device = load_model("config", "Device")
    WHOISInfo = load_model("config", "WHOISInfo")
    active_devices = Device.objects.filter(
        _is_deactivated=False, last_ip=OuterRef("ip_address")
    )
    now = timezone.now()
    referenced = WHOISInfo.objects.filter(Exists(active_devices))
    referenced.update(unreferenced_since=None)
    WHOISInfo.objects.filter(
        ~Exists(active_devices), unreferenced_since__isnull=True
    ).update(unreferenced_since=now)
    cutoff = now - timedelta(days=app_settings.WHOIS_REFRESH_THRESHOLD_DAYS)
    deleted, _ = WHOISInfo.objects.filter(
        ~Exists(active_devices), unreferenced_since__lte=cutoff
    ).delete()
    logger.info("Deleted %d expired unreferenced WHOIS record(s).", deleted)
    return deleted


@shared_task
def delete_whois_record(ip_address, force=False):
    """
    Deletes the WHOIS record for the device's last IP address.
    This is used when the device is deleted or its last IP address is changed.
    'force' parameter is used to delete the record without checking for linked devices.
    """
    WHOISInfo = load_model("config", "WHOISInfo")
    queryset = WHOISInfo.objects.filter(ip_address=ip_address)
    if force:
        queryset.delete()
    else:
        from .service import WHOISService

        WHOISService.reconcile_whois_references([ip_address])
