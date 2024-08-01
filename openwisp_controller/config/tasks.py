import logging

import requests
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from swapper import load_model

from openwisp_utils.tasks import OpenwispCeleryTask

logger = logging.getLogger(__name__)


@shared_task(soft_time_limit=7200)
def update_template_related_config_status(template_pk):
    """
    Flags config objects related to the specified
    template PK as modified and triggers config
    modified and config status changed signals
    """
    Template = load_model('config', 'Template')
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
            'soft time limit hit while executing '
            f'_update_related_config_status for {template} '
            f'(ID: {template_pk})'
        )


@shared_task(soft_time_limit=1200)
def create_vpn_dh(vpn_pk):
    """
    Generates DH parameters
    """
    Vpn = load_model('config', 'Vpn')
    vpn = Vpn.objects.get(pk=vpn_pk)
    try:
        vpn.dh = Vpn.dhparam(2048)
    except SoftTimeLimitExceeded:
        logger.error(
            'soft time limit hit while generating DH '
            f'parameters for VPN Server {vpn} (ID: {vpn_pk})'
        )
    else:
        vpn.full_clean()
        vpn.save()


@shared_task(soft_time_limit=7200)
def invalidate_devicegroup_cache_change(instance_id, model_name):
    from .api.views import DeviceGroupCommonName

    Device = load_model('config', 'Device')
    DeviceGroup = load_model('config', 'DeviceGroup')
    Cert = load_model('django_x509', 'Cert')

    if model_name == Device._meta.model_name:
        DeviceGroupCommonName.device_change_invalidates_cache(instance_id)
    elif model_name == DeviceGroup._meta.model_name:
        DeviceGroupCommonName.devicegroup_change_invalidates_cache(instance_id)
    elif model_name == Cert._meta.model_name:
        DeviceGroupCommonName.certificate_change_invalidates_cache(instance_id)


@shared_task(soft_time_limit=7200)
def invalidate_vpn_server_devices_cache_change(vpn_pk):
    Vpn = load_model('config', 'Vpn')
    VpnClient = load_model('config', 'VpnClient')
    vpn = Vpn.objects.get(pk=vpn_pk)
    VpnClient.invalidate_clients_cache(vpn)


@shared_task(soft_time_limit=7200)
def invalidate_devicegroup_cache_delete(instance_id, model_name, **kwargs):
    from .api.views import DeviceGroupCommonName

    DeviceGroup = load_model('config', 'DeviceGroup')
    Cert = load_model('django_x509', 'Cert')

    if model_name == DeviceGroup._meta.model_name:
        DeviceGroupCommonName.devicegroup_delete_invalidates_cache(
            kwargs['organization_id']
        )
    elif model_name == Cert._meta.model_name:
        DeviceGroupCommonName.certificate_delete_invalidates_cache(
            kwargs['organization_id'], kwargs['common_name']
        )


@shared_task(base=OpenwispCeleryTask)
def trigger_vpn_server_endpoint(endpoint, auth_token, vpn_id):
    response = requests.post(
        endpoint,
        params={'key': auth_token},
        verify=False if getattr(settings, 'DEBUG') else True,
    )
    if response.status_code == 200:
        logger.info(f'Triggered update webhook of VPN Server UUID: {vpn_id}')
    else:
        logger.error(
            'Failed to update VPN Server configuration. '
            f'Response status code: {response.status_code}, '
            f'VPN Server UUID: {vpn_id}',
        )


@shared_task(soft_time_limit=7200)
def change_devices_templates(instance_id, model_name, **kwargs):
    Device = load_model('config', 'Device')
    DeviceGroup = load_model('config', 'DeviceGroup')
    Config = load_model('config', 'Config')
    if model_name == Device._meta.model_name:
        Device.manage_devices_group_templates(
            device_ids=instance_id,
            old_group_ids=kwargs.get('old_group_id'),
            group_id=kwargs.get('group_id'),
        )

    elif model_name == DeviceGroup._meta.model_name:
        DeviceGroup.manage_group_templates(
            group_id=instance_id,
            old_template_ids=kwargs.get('old_templates'),
            template_ids=kwargs.get('templates'),
        )

    elif model_name == Config._meta.model_name:
        Config.manage_backend_changed(
            instance_id=instance_id,
            old_backend=kwargs.pop('old_backend'),
            backend=kwargs.pop('backend'),
            **kwargs,
        )


@shared_task(soft_time_limit=7200)
def bulk_invalidate_config_get_cached_checksum(query_params):
    Config = load_model('config', 'Config')
    Config.bulk_invalidate_get_cached_checksum(query_params)


@shared_task(base=OpenwispCeleryTask)
def invalidate_device_checksum_view_cache(organization_id):
    from .controller.views import DeviceChecksumView

    Device = load_model('config', 'Device')
    for device in (
        Device.objects.filter(organization_id=organization_id).only('id').iterator()
    ):
        DeviceChecksumView.invalidate_get_device_cache(device)
