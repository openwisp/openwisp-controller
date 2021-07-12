from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from openwisp_notifications.signals import notify
from swapper import load_model

from . import tasks
from .signals import config_status_changed, device_registered

Config = load_model('config', 'Config')
Device = load_model('config', 'Device')
DeviceGroup = load_model('config', 'DeviceGroup')
Organization = load_model('openwisp_users', 'Organization')
Cert = load_model('django_x509', 'Cert')


@receiver(
    config_status_changed,
    sender=Config,
    dispatch_uid='config_status_error_notification',
)
def config_status_error_notification(sender, instance, **kwargs):
    """
    Creates notification when status of a configuration changes to "error".
    """
    if instance.status == 'error':
        notify.send(sender=instance, type='config_error', target=instance.device)


@receiver(
    device_registered, sender=Device, dispatch_uid='device_registered_notification'
)
def device_registered_notification(sender, instance, is_new, **kwargs):
    """
    Creates notification when a new device is registered automatically
    through controller.
    """
    condition = _('A new') if is_new else _('The existing')
    notify.send(
        sender=instance, type='device_registered', target=instance, condition=condition
    )


def devicegroup_change_handler(instance, **kwargs):
    if 'created' in kwargs and kwargs['created'] is True:
        return
    model_name = instance._meta.model_name
    tasks.invalidate_devicegroup_cache.delay(instance.id, model_name)
