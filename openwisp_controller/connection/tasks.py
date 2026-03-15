import logging
import time
import uuid

import swapper
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from swapper import load_model

from . import settings as app_settings
from .connectors.exceptions import CommandTimeoutException
from .exceptions import NoWorkingDeviceConnectionError

logger = logging.getLogger(__name__)
_UPDATE_CONFIG_LOCK_KEY = "ow_update_config_{device_id}"
# Lock timeout (in seconds) acts as a safety net to release the lock
# in case the task crashes without proper cleanup.
_UPDATE_CONFIG_LOCK_TIMEOUT = 300


def _acquire_update_config_lock(device_id):
    """
    Attempts to atomically acquire a per-device lock using the Django cache.
    Returns a unique token string if the lock was acquired, None otherwise.
    The token must be passed to _release_update_config_lock to ensure
    only the lock owner can release it.
    """
    lock_key = _UPDATE_CONFIG_LOCK_KEY.format(device_id=device_id)
    token = str(uuid.uuid4())
    # cache.add is atomic: returns True only if the key doesn't already exist
    if cache.add(lock_key, token, timeout=_UPDATE_CONFIG_LOCK_TIMEOUT):
        return token
    return None


def _release_update_config_lock(device_id, token):
    """
    Releases the per-device update_config lock only if the caller
    owns it (i.e. the stored token matches).
    """
    lock_key = _UPDATE_CONFIG_LOCK_KEY.format(device_id=device_id)
    stored_token = cache.get(lock_key)
    if stored_token == token:
        cache.delete(lock_key)


@shared_task
def update_config(device_id):
    """
    Launches the ``update_config()`` operation
    of a specific device in the background
    """
    Device = swapper.load_model(*swapper.split(app_settings.UPDATE_CONFIG_MODEL))
    DeviceConnection = swapper.load_model("connection", "DeviceConnection")
    # wait for the saving operations of this device to complete
    # (there may be multiple ones happening at the same time)
    time.sleep(2)
    try:
        device = Device.objects.select_related("config").get(pk=device_id)
        # abort operation if device shouldn't be updated
        if not device.can_be_updated():
            logger.info(f"{device} (pk: {device_id}) is not going to be updated")
            return
    except ObjectDoesNotExist as e:
        logger.warning(f'update_config("{device_id}") failed: {e}')
        return
    lock_token = _acquire_update_config_lock(device_id)
    if not lock_token:
        logger.info(
            f"update_config for device {device_id} is already in progress, skipping"
        )
        return
    try:
        try:
            device_conn = DeviceConnection.get_working_connection(device)
        except NoWorkingDeviceConnectionError as e:
            logger.warning(
                f"update_config for device {device_id}: "
                f"DeviceConnection.get_working_connection failed: {e}"
            )
            return
        else:
            logger.info(f"Updating {device} (pk: {device_id})")
            device_conn.update_config()
    finally:
        _release_update_config_lock(device_id, lock_token)


# task timeout is SSH_COMMAND_TIMEOUT plus a 20% margin
@shared_task(soft_time_limit=app_settings.SSH_COMMAND_TIMEOUT * 1.2)
def launch_command(command_id):
    """
    Launches execution of commands in the background
    """
    Command = load_model("connection", "Command")
    try:
        command = Command.objects.get(pk=command_id)
    except Command.DoesNotExist as e:
        logger.warning(f'launch_command("{command_id}") failed: {e}')
        return
    try:
        command.execute()
    except SoftTimeLimitExceeded:
        command.status = "failed"
        command._add_output(_("Background task time limit exceeded."))
        command.save()
    except CommandTimeoutException as e:
        command.status = "failed"
        command._add_output(_(f"The command took longer than expected: {e}"))
        command.save()
    except Exception as e:
        logger.exception(
            f"An exception was raised while executing command {command_id}"
        )
        command.status = "failed"
        command._add_output(_(f"Internal system error: {e}"))
        command.save()


@shared_task(soft_time_limit=3600)
def auto_add_credentials_to_devices(credential_id, organization_id):
    Credentials = load_model("connection", "Credentials")
    Credentials.auto_add_to_devices(credential_id, organization_id)
