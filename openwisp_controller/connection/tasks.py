import logging
from time import sleep

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from swapper import load_model

Device = load_model('config', 'Device')
logger = logging.getLogger(__name__)


@shared_task
def update_config(device_id):
    """
    Launches the ``update_config()`` operation
    of a specific device in the background
    """
    # wait for the saving operations of this device to complete
    # (there may be multiple ones happening at the same time)
    sleep(2)
    # avoid repeating the operation multiple times
    device = Device.objects.select_related('config').get(pk=device_id)
    try:
        if device.config.status == 'applied':
            return
    except ObjectDoesNotExist:
        logger.warning(f'Config with device id: {device_id} does not exist')
        return
    qs = device.deviceconnection_set.filter(device_id=device_id, enabled=True)
    conn = qs.first()
    if conn:
        conn.update_config()
