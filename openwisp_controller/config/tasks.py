import logging
from http import HTTPStatus

import requests
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from openwisp_notifications.signals import notify
from requests.exceptions import RequestException
from swapper import load_model

from openwisp_controller.config.api.zerotier_service import ZerotierService
from openwisp_utils.tasks import OpenwispCeleryTask

from .settings import API_TASK_RETRY_OPTIONS

logger = logging.getLogger(__name__)


class OpenwispApiTask(OpenwispCeleryTask):

    _RECOVERABLE_API_CODES = [
        HTTPStatus.TOO_MANY_REQUESTS,  # 429
        HTTPStatus.INTERNAL_SERVER_ERROR,  # 500
        HTTPStatus.BAD_GATEWAY,  # 502
        HTTPStatus.SERVICE_UNAVAILABLE,  # 503
        HTTPStatus.GATEWAY_TIMEOUT,  # 504
    ]

    def _send_api_task_notification(self, type, **kwargs):
        vpn = kwargs.get('instance')
        action = kwargs.get('action').replace('_', ' ')
        status_code = kwargs.get('status_code')
        delete_key_type = 'error' if type == 'recovery' else 'recovery'
        if cache.add(f'{self.name}_{vpn.id}_{type}', True, None):
            # TODO: Remove this time delay
            import time

            time.sleep(4)
            notify.send(
                type=f'api_task_{type}',
                sender=vpn,
                target=vpn,
                action=action,
                status_code=status_code,
            )
            cache.delete(f'{self.name}_{vpn.id}_{delete_key_type}')

    def handle_api_call(self, fn, *args, send_notification=True, **kwargs):
        updated_config = None
        response = fn(*args)
        if isinstance(response, tuple):
            response, updated_config = response
        try:
            response.raise_for_status()
            logger.info(kwargs.get('info'))
            if send_notification:
                self._send_api_task_notification(type='recovery', **kwargs)
            return (response, updated_config) if updated_config else response
        except RequestException as exc:
            if response.status_code in self._RECOVERABLE_API_CODES:
                logger.error(f'{kwargs.get("err")}, Error: {str(exc)}')
                cache.delete(f'{self.name}_{kwargs.get("instance").id}_recovery')
                raise exc
            logger.error(f'{kwargs.get("err")}, Error: {str(exc)}')
            if send_notification:
                self._send_api_task_notification(
                    type='error', status_code=response.status_code, **kwargs
                )


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


@shared_task(base=OpenwispCeleryTask)
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


@shared_task(base=OpenwispCeleryTask)
def invalidate_vpn_server_devices_cache_change(vpn_pk):
    Vpn = load_model('config', 'Vpn')
    VpnClient = load_model('config', 'VpnClient')
    vpn = Vpn.objects.get(pk=vpn_pk)
    VpnClient.invalidate_clients_cache(vpn)


@shared_task(base=OpenwispCeleryTask)
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


@shared_task(
    bind=True,
    base=OpenwispApiTask,
    autoretry_for=(RequestException,),
    **API_TASK_RETRY_OPTIONS,
)
def trigger_zerotier_server_update(self, config, vpn_id):
    Vpn = load_model('config', 'Vpn')
    vpn = Vpn.objects.get(pk=vpn_id)
    service_method = ZerotierService(
        vpn.host, vpn.auth_token, vpn.subnet, vpn.ip
    ).update_network
    response, updated_config = self.handle_api_call(
        service_method,
        config,
        vpn.network_id,
        instance=vpn,
        action='update',
        info=(
            f'Successfully updated the configuration of '
            f'ZeroTier VPN Server with UUID: {vpn_id}'
        ),
        err=(
            f'Failed to update ZeroTier VPN Server configuration, '
            f'VPN Server UUID: {vpn_id}'
        ),
    )
    if response.ok:
        vpn.network_id = updated_config.pop('id', None)
        vpn.config = {**vpn.config, 'zerotier': [updated_config]}
        # Update zerotier network controller
        trigger_zerotier_server_update_member.delay(vpn_id)


@shared_task(
    bind=True,
    base=OpenwispApiTask,
    autoretry_for=(RequestException,),
    **API_TASK_RETRY_OPTIONS,
)
def trigger_zerotier_server_update_member(self, vpn_id):
    Vpn = load_model('config', 'Vpn')
    vpn = Vpn.objects.get(pk=vpn_id)
    service_method = ZerotierService(
        vpn.host,
        vpn.auth_token,
        ip=vpn.ip,
    ).update_network_member
    self.handle_api_call(
        service_method,
        vpn.node_id,
        vpn.network_id,
        instance=vpn,
        action='update_member',
        info=(
            f'Successfully updated ZeroTier network member: {vpn.node_id}, '
            f'ZeroTier network: {vpn.network_id}, '
            f'ZeroTier VPN server UUID: {vpn_id}'
        ),
        err=(
            f'Failed to update ZeroTier network member: {vpn.node_id}, '
            f'ZeroTier network: {vpn.network_id}, '
            f'ZeroTier VPN server UUID: {vpn_id}'
        ),
    )


@shared_task(
    bind=True,
    base=OpenwispApiTask,
    autoretry_for=(RequestException,),
    **API_TASK_RETRY_OPTIONS,
)
def trigger_zerotier_server_join(self, vpn_id):
    Vpn = load_model('config', 'Vpn')
    vpn = Vpn.objects.get(pk=vpn_id)
    service_method = ZerotierService(
        vpn.host,
        vpn.auth_token,
    ).join_network
    response = self.handle_api_call(
        service_method,
        vpn.network_id,
        instance=vpn,
        action='network_join',
        info=(
            f'Successfully joined the ZeroTier network: {vpn.network_id}, '
            f'ZeroTier VPN Server UUID: {vpn_id}'
        ),
        err=(
            f'Failed to join ZeroTier network: {vpn.network_id}, '
            f'VPN Server UUID: {vpn_id}'
        ),
    )
    if response.ok:
        # Update zerotier network controller
        trigger_zerotier_server_update_member.delay(vpn_id)


@shared_task(
    bind=True,
    base=OpenwispApiTask,
    autoretry_for=(RequestException,),
    **API_TASK_RETRY_OPTIONS,
)
def trigger_zerotier_server_delete(self, host, auth_token, network_id, vpn_id):
    service_method = ZerotierService(host, auth_token).delete_network
    self.handle_api_call(
        service_method,
        network_id,
        info=(f'Successfully deleted the ZeroTier VPN Server with UUID: {vpn_id}'),
        err='ZeroTier VPN Server does not exist',
        send_notification=False,
    )


@shared_task(base=OpenwispCeleryTask)
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
