import logging

import requests
from celery import shared_task
from django.core.cache import cache
from django.utils.translation import gettext as _
from geoip2 import errors
from geoip2 import webservice as geoip2_webservice
from openwisp_notifications.signals import notify
from swapper import load_model

from openwisp_controller.config import settings as app_settings
from openwisp_utils.tasks import OpenwispCeleryTask

logger = logging.getLogger(__name__)


class WhoIsCeleryRetryTask(OpenwispCeleryTask):
    """
    Base class for OpenWISP Celery tasks with retry support on failure.
    """

    # this is the exception related to networking errors
    # that should trigger a retry of the task.
    autoretry_for = (errors.HTTPError,)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        Device = load_model("config", "Device")

        device_pk = kwargs.get("device_pk")
        new_ip_address = kwargs.get("new_ip_address")
        device = Device.objects.get(pk=device_pk)
        # Notify the user about the failure via web notification
        notify.send(
            sender=device,
            type="generic_message",
            target=device,
            action_object=device,
            level="error",
            message=_(
                "Failed to fetch WhoIs details for device"
                " [{notification.target}]({notification.target_link})"
            ),
            description=_(
                f"WhoIs details could not be fetched for ip: {new_ip_address}.\n"
                f"Details: {exc}"
            ),
        )
        logger.error(f"WhoIs lookup failed for : {device_pk} for IP: {new_ip_address}.")
        return super().on_failure(exc, task_id, args, kwargs, einfo)


# device_pk is used when task fails to report for which device failure occurred
@shared_task(
    bind=True,
    base=WhoIsCeleryRetryTask,
    **app_settings.API_TASK_RETRY_OPTIONS,
)
def fetch_whois_details(self, device_pk, initial_ip_address, new_ip_address):
    """
    Fetches the WhoIs details of the given IP address
    and creates/updates the WhoIs record.
    """
    WhoIsInfo = load_model("config", "WhoIsInfo")

    try:
        # Host is based on the db that is used to fetch the details.
        # As we are using GeoLite2, 'geolite.info' host is used.
        # Reference: https://geoip2.readthedocs.io/en/latest/#sync-web-service-example
        ip_client = geoip2_webservice.Client(
            account_id=app_settings.GEOIP_ACCOUNT_ID,
            license_key=app_settings.GEOIP_LICENSE_KEY,
            host="geolite.info",
        )

        data = ip_client.city(ip_address=new_ip_address)
        # Format address using the data from the geoip2 response
        address = {
            "city": getattr(data.city, "name", ""),
            "country": getattr(data.country, "name", ""),
            "continent": getattr(data.continent, "name", ""),
            "postal": str(getattr(data.postal, "code", "")),
        }
        # Create the WhoIs information
        WhoIsInfo.objects.create(
            organization_name=data.traits.autonomous_system_organization,
            asn=data.traits.autonomous_system_number,
            country=data.country.name,
            timezone=data.location.time_zone,
            address=address,
            cidr=data.traits.network,
            ip_address=new_ip_address,
        )
        logger.info(f"Successfully fetched WHOIS details for {new_ip_address}.")

        # not using the delete method of WhoIsService due to circular imports
        queryset = WhoIsInfo.objects.filter(ip_address=initial_ip_address)
        # the following check ensures that for a case when device last_ip
        # is not changed and there is no related whois record, we do not
        # delete the newly created record as both `initial_ip_address` and
        # `new_ip_address` would be same for such case. Also invalidate the cache
        if initial_ip_address != new_ip_address and queryset.exists():
            # If any active devices are linked to the following record,
            # then they will trigger this task and new record gets created
            # with latest data.
            queryset.delete()
            cache.delete(f"whois_info:{initial_ip_address}")

    # Catching all possible exceptions raised by the geoip2 client
    # logging the exceptions and raising them with appropriate messages
    except errors.AddressNotFoundError:
        message = _(f"No WHOIS information found for IP address {new_ip_address}.")
        logger.error(message)
        raise errors.AddressNotFoundError(message)
    except errors.AuthenticationError:
        message = _(
            "Authentication failed for GeoIP2 service. "
            "Check your OPENWISP_CONTROLLER_GEOIP_ACCOUNT_ID and "
            "OPENWISP_CONTROLLER_GEOIP_LICENSE_KEY settings."
        )
        logger.error(message)
        raise errors.AuthenticationError(message)
    except errors.OutOfQueriesError:
        message = _("Your account has run out of queries for the GeoIP2 service.")
        logger.error(message)
        raise errors.OutOfQueriesError(message)
    except errors.PermissionRequiredError:
        message = _("Your account does not have permission to access this service.")
        logger.error(message)
        raise errors.PermissionRequiredError(message)
    except requests.RequestException as e:
        logger.error(f"Error fetching WHOIS details for {new_ip_address}: {e}")
        raise e
