import logging
import time

import swapper
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from swapper import load_model

from . import settings as app_settings

logger = logging.getLogger(__name__)


@shared_task
def update_config(device_id):
    """
    Launches the ``update_config()`` operation
    of a specific device in the background
    """
    Device = swapper.load_model(*swapper.split(app_settings.UPDATE_CONFIG_MODEL))
    # wait for the saving operations of this device to complete
    # (there may be multiple ones happening at the same time)
    time.sleep(2)
    try:
        device = Device.objects.select_related('config').get(pk=device_id)
        # abort operation if device shouldn't be updated
        if not device.can_be_updated():
            logger.info(f'{device} (pk: {device_id}) is not going to be updated')
            return
    except ObjectDoesNotExist as e:
        logger.warning(f'update_config("{device_id}") failed: {e}')
        return
    qs = device.deviceconnection_set.filter(device_id=device_id, enabled=True)
    conn = qs.first()
    if conn:
        logger.info(f'Updating {device} (pk: {device_id})')
        conn.update_config()


# task timeout is SSH_COMMAND_TIMEOUT plus a 20% margin
@shared_task(soft_time_limit=app_settings.SSH_COMMAND_TIMEOUT * 1.2)
def launch_command(command_id):
    """
    Launches execution of commands in the background
    """
    Command = load_model('connection', 'Command')
    try:
        command = Command.objects.get(pk=command_id)
    except Command.DoesNotExist as e:
        logger.warning(f'launch_command("{command_id}") failed: {e}')
        return
    try:
        command.execute()
    except SoftTimeLimitExceeded:
        command.status = 'failed'
        command._add_output(_('Background task time limit exceeded.'))
        command.save()
    except Exception as e:
        logger.exception(
            f'An exception was raised while executing command {command_id}'
        )
        command.status = 'failed'
        command._add_output(_(f'Internal system error: {e}'))
        command.save()


@shared_task(soft_time_limit=180)
def auto_add_credentials_to_devices(credential_id, organization_id):
    Credentials = load_model('connection', 'Credentials')
    Credentials.auto_add_to_devices(credential_id, organization_id)
