import logging

import requests
from celery import shared_task
from django.utils.translation import gettext as _
from geoip2 import errors
from geoip2 import webservice as geoip2_webservice
from openwisp_notifications.signals import notify
from swapper import load_model

from openwisp_utils.tasks import OpenwispCeleryTask

from .. import settings as app_settings

logger = logging.getLogger(__name__)

EXCEPTION_MESSAGES = {
    errors.AddressNotFoundError: _(
        "No WHOIS information found for IP address {ip_address}"
    ),
    errors.AuthenticationError: _(
        "Authentication failed for GeoIP2 service. "
        "Check your OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT and "
        "OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY settings."
    ),
    errors.OutOfQueriesError: _(
        "Your account has run out of queries for the GeoIP2 service."
    ),
    errors.PermissionRequiredError: _(
        "Your account does not have permission to access this service."
    ),
}


class WHOISCeleryRetryTask(OpenwispCeleryTask):
    """
    Base class for OpenWISP Celery tasks with retry support on failure.
    """

    # this is the exception related to networking errors
    # that should trigger a retry of the task.
    autoretry_for = (errors.HTTPError,)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Notify the user about the failure of the WHOIS task."""
        Device = load_model("config", "Device")

        device_pk = kwargs.get("device_pk")
        new_ip_address = kwargs.get("new_ip_address")
        device = Device.objects.get(pk=device_pk)

        notify.send(
            sender=device,
            type="generic_message",
            target=device,
            action_object=device,
            level="error",
            message=_(
                "Failed to fetch WHOIS details for device"
                " [{notification.target}]({notification.target_link})"
            ),
            description=_(
                f"WHOIS details could not be fetched for ip: {new_ip_address}."
            ),
        )
        logger.error(f"WHOIS lookup failed. Details: {exc}")
        return super().on_failure(exc, task_id, args, kwargs, einfo)


# device_pk is used when task fails to report for which device failure occurred
@shared_task(
    bind=True,
    base=WHOISCeleryRetryTask,
    **app_settings.API_TASK_RETRY_OPTIONS,
)
def fetch_whois_details(self, device_pk, initial_ip_address, new_ip_address):
    """
    Fetches the WHOIS details of the given IP address
    and creates/updates the WHOIS record.
    """
    WHOISInfo = load_model("config", "WHOISInfo")

    # The task can be triggered for same ip address multiple times
    # so we need to return early if WHOIS is already created.
    if WHOISInfo.objects.filter(ip_address=new_ip_address).exists():
        return

    # Host is based on the db that is used to fetch the details.
    # As we are using GeoLite2, 'geolite.info' host is used.
    # Refer: https://geoip2.readthedocs.io/en/latest/#sync-web-service-example
    ip_client = geoip2_webservice.Client(
        account_id=app_settings.WHOIS_GEOIP_ACCOUNT,
        license_key=app_settings.WHOIS_GEOIP_KEY,
        host="geolite.info",
    )

    try:
        data = ip_client.city(ip_address=new_ip_address)

    # Catching all possible exceptions raised by the geoip2 client
    # and raising them with appropriate messages to be handled by the task
    # retry mechanism.
    except (
        errors.AddressNotFoundError,
        errors.AuthenticationError,
        errors.OutOfQueriesError,
        errors.PermissionRequiredError,
    ) as e:
        exc_type = type(e)
        message = EXCEPTION_MESSAGES.get(exc_type)
        if exc_type is errors.AddressNotFoundError:
            message = message.format(ip_address=new_ip_address)
        raise exc_type(message)
    except requests.RequestException as e:
        raise e

    else:
        # The attributes are always present in the response,
        # but they can be None, so added fallbacks.
        address = {
            "city": data.city.name or "",
            "country": data.country.name or "",
            "continent": data.continent.name or "",
            "postal": str(data.postal.code or ""),
        }

        whois_obj = WHOISInfo(
            isp=data.traits.autonomous_system_organization,
            asn=data.traits.autonomous_system_number,
            timezone=data.location.time_zone,
            address=address,
            cidr=data.traits.network,
            ip_address=new_ip_address,
        )
        whois_obj.full_clean()
        whois_obj.save()
        logger.info(f"Successfully fetched WHOIS details for {new_ip_address}.")

        # the following check ensures that for a case when device last_ip
        # is not changed and there is no related WHOIS record, we do not
        # delete the newly created record as both `initial_ip_address` and
        # `new_ip_address` would be same for such case.
        if initial_ip_address != new_ip_address:
            # If any active devices are linked to the following record,
            # then they will trigger this task and new record gets created
            # with latest data.
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
