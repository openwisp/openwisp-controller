import logging
from http import HTTPStatus
from time import sleep

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
        # Adding some delay here to prevent overlapping
        # of the django success message container
        # with the ow-notification container
        # https://github.com/openwisp/openwisp-notifications/issues/264
        sleep(2)
        notify.send(
            type=f'api_task_{type}',
            sender=vpn,
            target=vpn,
            action=action,
            status_code=status_code,
        )

    def handle_api_call(self, fn, *args, send_notification=True, **kwargs):
        """
        This method handles API calls and their responses
        and triggers appropriate web notifications, which include:

        Error notification
          - Sent on any unrecoverable API call failure
        Recovery notification
          - Sent only when an error notification was previously triggered

        Also raises an exception for recoverable
        API calls leading to the retrying of the API task

        NOTE: The method utilizes a cache key
        to prevent flooding of similar task notifications

        Parameters:
            fn: API service method
            *args: Arguments for the API service method
            send_notification: If True, send notifications for API tasks
            **kwargs: Arguments used by the _send_api_task_notification method
        """
        updated_config = None
        err_msg = kwargs.get('err')
        info_msg = kwargs.get('info')
        vpn = kwargs.get('instance')
        if send_notification:
            task_key = f'{self.name}_{vpn.pk.hex}_last_operation'
        # Execute API call and get response
        response = fn(*args)
        if isinstance(response, tuple):
            response, updated_config = response
        try:
            response.raise_for_status()
            logger.info(info_msg)
            if send_notification:
                task_result = cache.get(task_key)
                if task_result == 'error':
                    self._send_api_task_notification('recovery', **kwargs)
                    cache.set(task_key, 'success', None)
        except RequestException as exc:
            if response.status_code in self._RECOVERABLE_API_CODES:
                retry_logger = logger.warn
                # When retry limit is reached, use error logging
                if self.request.retries == self.max_retries:
                    retry_logger = logger.error
                retry_logger(
                    f'Try [{self.request.retries}/{self.max_retries}] '
                    f'{err_msg}, Error: {exc}'
                )
                raise exc
            logger.error(f'{err_msg}, Error: {exc}')
            if send_notification:
                task_result = cache.get(task_key)
                if task_result in (None, 'success'):
                    cache.set(task_key, 'error', None)
                    self._send_api_task_notification(
                        'error', status_code=response.status_code, **kwargs
                    )
        return (response, updated_config) if updated_config else response


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
    network_id = vpn.network_id
    service_method = ZerotierService(
        vpn.host, vpn.auth_token, vpn.subnet.subnet
    ).update_network
    response, updated_config = self.handle_api_call(
        service_method,
        config,
        network_id,
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
    if response.status_code == 200:
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
def trigger_zerotier_server_update_member(self, vpn_id, ip=None, node_id=None):
    Vpn = load_model('config', 'Vpn')
    vpn = Vpn.objects.get(pk=vpn_id)
    network_id = vpn.network_id
    node_id = node_id or vpn.node_id
    member_ip = ip or vpn.ip.ip_address
    service_method = ZerotierService(
        vpn.host,
        vpn.auth_token,
    ).update_network_member
    self.handle_api_call(
        service_method,
        node_id,
        network_id,
        member_ip,
        instance=vpn,
        action='update_member',
        info=(
            f'Successfully updated ZeroTier network member: {node_id}, '
            f'ZeroTier network: {network_id}, '
            f'ZeroTier VPN server UUID: {vpn_id}'
        ),
        err=(
            f'Failed to update ZeroTier network member: {node_id}, '
            f'ZeroTier network: {network_id}, '
            f'ZeroTier VPN server UUID: {vpn_id}'
        ),
    )


@shared_task(
    bind=True,
    base=OpenwispApiTask,
    autoretry_for=(RequestException,),
    **API_TASK_RETRY_OPTIONS,
)
def trigger_zerotier_server_leave_member(self, vpn_id, node_id=None):
    Vpn = load_model('config', 'Vpn')
    vpn = Vpn.objects.get(pk=vpn_id)
    network_id = vpn.network_id
    service_method = ZerotierService(
        vpn.host,
        vpn.auth_token,
    ).leave_network_member
    self.handle_api_call(
        service_method,
        node_id,
        network_id,
        instance=vpn,
        action='leave_member',
        info=(
            f'Successfully left ZeroTier Network with ID: {network_id}, '
            f'ZeroTier Member ID: {node_id}, '
            f'ZeroTier VPN server UUID: {vpn_id}'
        ),
        err=(
            f'Failed to leave ZeroTier Network with ID: {network_id}, '
            f'ZeroTier Member ID: {node_id}, '
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
    network_id = vpn.network_id
    service_method = ZerotierService(
        vpn.host,
        vpn.auth_token,
    ).join_network
    response = self.handle_api_call(
        service_method,
        network_id,
        instance=vpn,
        action='network_join',
        info=(
            f'Successfully joined the ZeroTier network: {network_id}, '
            f'ZeroTier VPN Server UUID: {vpn_id}'
        ),
        err=(
            f'Failed to join ZeroTier network: {network_id}, '
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
    response = self.handle_api_call(
        service_method,
        network_id,
        info=(
            f'Successfully deleted the ZeroTier VPN Server '
            f'with UUID: {vpn_id}, Network ID: {network_id}'
        ),
        err=(
            'Failed to delete ZeroTier VPN Server '
            f'with UUID: {vpn_id}, Network ID: {network_id}, '
            'as it does not exist on the ZeroTier Controller Networks'
        ),
        send_notification=False,
    )
    # In case of successful deletion of the network
    # we should also remove controller node from the network
    if response.status_code == 200:
        trigger_zerotier_server_leave.delay(host, auth_token, network_id)


@shared_task(
    bind=True,
    base=OpenwispApiTask,
    autoretry_for=(RequestException,),
    **API_TASK_RETRY_OPTIONS,
)
def trigger_zerotier_server_leave(self, host, auth_token, network_id):
    service_method = ZerotierService(host, auth_token).leave_network
    self.handle_api_call(
        service_method,
        network_id,
        info=f'Successfully left the ZeroTier Network with ID: {network_id}',
        err=f'Failed to leave ZeroTier Network with ID: {network_id}',
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
