import logging

import requests
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext as _
from geoip2 import errors
from geoip2 import webservice as geoip2_webservice
from openwisp_notifications.signals import notify
from swapper import load_model

from openwisp_utils.tasks import OpenwispCeleryTask

from . import settings as app_settings

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
                f"WhoIs details could not be fetched for ip: {new_ip_address}."
                f" Details:{exc}"
            ),
        )
        logger.error(f"WhoIs lookup failed for : {device_pk} for IP: {new_ip_address}.")
        return super().on_failure(exc, task_id, args, kwargs, einfo)


@shared_task(soft_time_limit=7200)
def update_template_related_config_status(template_pk):
    """
    Flags config objects related to the specified
    template PK as modified and triggers config
    modified and config status changed signals
    """
    Template = load_model("config", "Template")
    try:
        template = Template.objects.get(pk=template_pk)
    except ObjectDoesNotExist as e:
        logger.warning(
            f'update_template_related_config_status("{template_pk}") failed: {e}'
        )
        return
    try:
        template._update_related_config_status()
    except SoftTimeLimitExceeded:
        logger.error(
            "soft time limit hit while executing "
            f"_update_related_config_status for {template} "
            f"(ID: {template_pk})"
        )


@shared_task(soft_time_limit=1200)
def create_vpn_dh(vpn_pk):
    """
    Generates DH parameters
    """
    Vpn = load_model("config", "Vpn")
    vpn = Vpn.objects.get(pk=vpn_pk)
    try:
        vpn.dh = Vpn.dhparam(2048)
    except SoftTimeLimitExceeded:
        logger.error(
            "soft time limit hit while generating DH "
            f"parameters for VPN Server {vpn} (ID: {vpn_pk})"
        )
    else:
        vpn.full_clean()
        vpn.save()


@shared_task(soft_time_limit=7200)
def invalidate_devicegroup_cache_change(instance_id, model_name):
    from .api.views import DeviceGroupCommonName

    Device = load_model("config", "Device")
    DeviceGroup = load_model("config", "DeviceGroup")
    Cert = load_model("django_x509", "Cert")

    if model_name == Device._meta.model_name:
        DeviceGroupCommonName.device_change_invalidates_cache(instance_id)
    elif model_name == DeviceGroup._meta.model_name:
        DeviceGroupCommonName.devicegroup_change_invalidates_cache(instance_id)
    elif model_name == Cert._meta.model_name:
        DeviceGroupCommonName.certificate_change_invalidates_cache(instance_id)


@shared_task(soft_time_limit=7200)
def invalidate_vpn_server_devices_cache_change(vpn_pk):
    Vpn = load_model("config", "Vpn")
    VpnClient = load_model("config", "VpnClient")
    vpn = Vpn.objects.get(pk=vpn_pk)
    VpnClient.invalidate_clients_cache(vpn)


@shared_task(soft_time_limit=7200)
def invalidate_devicegroup_cache_delete(instance_id, model_name, **kwargs):
    from .api.views import DeviceGroupCommonName

    DeviceGroup = load_model("config", "DeviceGroup")
    Cert = load_model("django_x509", "Cert")

    if model_name == DeviceGroup._meta.model_name:
        DeviceGroupCommonName.devicegroup_delete_invalidates_cache(
            kwargs["organization_id"]
        )
    elif model_name == Cert._meta.model_name:
        DeviceGroupCommonName.certificate_delete_invalidates_cache(
            kwargs["organization_id"], kwargs["common_name"]
        )


@shared_task(base=OpenwispCeleryTask)
def trigger_vpn_server_endpoint(endpoint, auth_token, vpn_id):
    response = requests.post(
        endpoint,
        params={"key": auth_token},
        verify=False if getattr(settings, "DEBUG") else True,
    )
    if response.status_code == 200:
        logger.info(f"Triggered update webhook of VPN Server UUID: {vpn_id}")
    else:
        logger.error(
            "Failed to update VPN Server configuration. "
            f"Response status code: {response.status_code}, "
            f"VPN Server UUID: {vpn_id}",
        )


@shared_task(soft_time_limit=7200)
def change_devices_templates(instance_id, model_name, **kwargs):
    Device = load_model("config", "Device")
    DeviceGroup = load_model("config", "DeviceGroup")
    Config = load_model("config", "Config")
    if model_name == Device._meta.model_name:
        Device.manage_devices_group_templates(
            device_ids=instance_id,
            old_group_ids=kwargs.get("old_group_id"),
            group_id=kwargs.get("group_id"),
        )

    elif model_name == DeviceGroup._meta.model_name:
        DeviceGroup.manage_group_templates(
            group_id=instance_id,
            old_template_ids=kwargs.get("old_templates"),
            template_ids=kwargs.get("templates"),
        )

    elif model_name == Config._meta.model_name:
        Config.manage_backend_changed(
            instance_id=instance_id,
            old_backend=kwargs.pop("old_backend"),
            backend=kwargs.pop("backend"),
            **kwargs,
        )


@shared_task(soft_time_limit=7200)
def bulk_invalidate_config_get_cached_checksum(query_params):
    Config = load_model("config", "Config")
    Config.bulk_invalidate_get_cached_checksum(query_params)


@shared_task(base=OpenwispCeleryTask)
def invalidate_device_checksum_view_cache(organization_id):
    from .controller.views import DeviceChecksumView

    Device = load_model("config", "Device")
    for device in (
        Device.objects.filter(organization_id=organization_id).only("id").iterator()
    ):
        DeviceChecksumView.invalidate_get_device_cache(device)


# device_pk is used when task fails to report for which device failure occurred
@shared_task(
    bind=True,
    base=WhoIsCeleryRetryTask,
    **app_settings.API_TASK_RETRY_OPTIONS,
)
def fetch_whois_details(self, device_pk, old_ip_address, new_ip_address):
    """
    Fetches the WhoIs details of the given IP address
    and creates/updates the WhoIs record.
    """
    WhoIsInfo = load_model("config", "WhoIsInfo")

    try:
        # 'geolite.info' host is used for GeoLite2
        # Reference: https://geoip2.readthedocs.io/en/latest/#sync-web-service-example
        ip_client = geoip2_webservice.Client(
            app_settings.GEOIP_ACCOUNT_ID,
            app_settings.GEOIP_LICENSE_KEY,
            "geolite.info",
        )

        data = ip_client.city(new_ip_address)
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

        # the following check ensures that for a case when device last_ip
        # is not changed and there is no related whois record, we do not
        # delete the newly created record as both `old_ip_address` and
        # `new_ip_address` would be same for such case.
        if old_ip_address != new_ip_address:
            # If any active devices are linked to the following record,
            # then they will trigger this task and new record gets created
            # with latest data.
            WhoIsInfo.objects.filter(ip_address=old_ip_address).delete()

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
