import logging
import time

import swapper
from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist

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
