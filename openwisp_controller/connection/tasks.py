import logging
import time

import swapper
from celery import current_app, shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from swapper import load_model

from . import settings as app_settings
from .connectors.exceptions import CommandTimeoutException
from .exceptions import NoWorkingDeviceConnectionError

logger = logging.getLogger(__name__)
_TASK_NAME = "openwisp_controller.connection.tasks.update_config"


def _is_update_in_progress(device_id, current_task_id=None):
    active = current_app.control.inspect().active()
    if not active:
        return False
    # check if there's any other running task before adding it
    # exclude the current task by comparing task IDs
    for task_list in active.values():
        for task in task_list:
            if (
                task["name"] == _TASK_NAME
                and str(device_id) in task["args"]
                and task["id"] != current_task_id
            ):
                return True
    return False


@shared_task(bind=True)
def update_config(self, device_id):
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
        if device.is_fully_deactivated():
            logger.info(f"{device} (pk: {device_id}) is deactivated, skipping update")
            return
        # abort operation if device shouldn't be updated
        if not device.can_be_updated():
            logger.info(f"{device} (pk: {device_id}) is not going to be updated")
            return
    except ObjectDoesNotExist as e:
        logger.warning(f'update_config("{device_id}") failed: {e}')
        return
    if _is_update_in_progress(device_id, current_task_id=self.request.id):
        return
    try:
        device_conn = DeviceConnection.get_working_connection(device)
    except NoWorkingDeviceConnectionError:
        return
    else:
        logger.info(f"Updating {device} (pk: {device_id})")
        device_conn.update_config()


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
        command._save_without_resurrecting()
    except CommandTimeoutException as e:
        command.status = "failed"
        command._add_output(_(f"The command took longer than expected: {e}"))
        command._save_without_resurrecting()
    except Exception as e:
        logger.exception(
            f"An exception was raised while executing command {command_id}"
        )
        command.status = "failed"
        command._add_output(_(f"Internal system error: {e}"))
        command._save_without_resurrecting()


@shared_task(bind=True, soft_time_limit=3600)
def launch_batch_command(self, batch_id):
    BatchCommand = load_model("connection", "BatchCommand")
    try:
        batch = BatchCommand.objects.get(pk=batch_id)
        batch.launch()
    except ObjectDoesNotExist:
        logger.warning(f"The BatchCommand object with id {batch_id} has been deleted")


@shared_task(soft_time_limit=3600)
def auto_add_credentials_to_devices(credential_id, organization_id):
    Credentials = load_model("connection", "Credentials")
    Credentials.auto_add_to_devices(credential_id, organization_id)
