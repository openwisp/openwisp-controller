import logging
from http import HTTPStatus
from time import sleep

from celery import shared_task
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
        except RequestException as e:
            if response.status_code in self._RECOVERABLE_API_CODES:
                retry_logger = logger.warn
                # When retry limit is reached, use error logging
                if self.request.retries == self.max_retries:
                    retry_logger = logger.error
                retry_logger(
                    f'Try [{self.request.retries}/{self.max_retries}] '
                    f'{err_msg}, Error: {e}'
                )
                raise e
            logger.error(f'{err_msg}, Error: {e}')
            if send_notification:
                task_result = cache.get(task_key)
                if task_result in (None, 'success'):
                    cache.set(task_key, 'error', None)
                    self._send_api_task_notification(
                        'error', status_code=response.status_code, **kwargs
                    )
        return (response, updated_config) if updated_config else response


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
def trigger_zerotier_server_remove_member(self, node_id=None, **vpn_kwargs):
    Vpn = load_model('config', 'Vpn')
    vpn_id = vpn_kwargs.get('id')
    host = vpn_kwargs.get('host')
    auth_token = vpn_kwargs.get('auth_token')
    network_id = vpn_kwargs.get('network_id')
    try:
        vpn = Vpn.objects.get(pk=vpn_id)
        notification_kwargs = dict(instance=vpn, action='remove_member')
    # When a ZeroTier VPN server is deleted
    # and this is followed by the deletion of ZeroTier VPN clients
    # we won't have access to the VPN server instance. Therefore, we should
    # refrain from sending a notification for the 'leave member' operation
    except ObjectDoesNotExist:
        notification_kwargs = dict(send_notification=False)
    service_method = ZerotierService(
        host,
        auth_token,
    ).remove_network_member
    self.handle_api_call(
        service_method,
        node_id,
        network_id,
        **notification_kwargs,
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
