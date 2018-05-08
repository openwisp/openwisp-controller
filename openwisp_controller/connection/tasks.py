from __future__ import absolute_import, unicode_literals

from time import sleep

from celery import shared_task

from ..config.models import Device


@shared_task
def update_config(device_id):
    """
    Launches the ``update_config()`` operation
    of a specific device in the background
    """
    # wait for the saving operations of this device to complete
    # (there may be multiple ones happening at the same time)
    sleep(4)
    # avoid repeating the operation multiple times
    device = Device.objects.select_related('config').get(pk=device_id)
    if device.config.status == 'running':
        return
    qs = device.deviceconnection_set.filter(device_id=device_id, enabled=True)
    if qs.count() > 0:
        conn = qs.first()
        conn.update_config()
