from django.db import transaction
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from openwisp_notifications.signals import notify
from swapper import load_model

from openwisp_controller.config.controller.views import DeviceChecksumView

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
    if type(instance) is list:
        # changes group templates for multiple devices
        devicegroup_templates_change_handler(instance, **kwargs)
        return
    if instance._state.adding or ('created' in kwargs and kwargs['created'] is True):
        return
    model_name = instance._meta.model_name
    if model_name == Device._meta.model_name:
        # remove old group templates and apply new group templates
        devicegroup_templates_change_handler(instance, **kwargs)
    tasks.invalidate_devicegroup_cache_change.delay(instance.id, model_name)


def devicegroup_delete_handler(instance, **kwargs):
    kwargs = {}
    model_name = instance._meta.model_name
    kwargs['organization_id'] = instance.organization_id
    if isinstance(instance, Cert):
        kwargs['common_name'] = instance.common_name
    tasks.invalidate_devicegroup_cache_delete.delay(instance.id, model_name, **kwargs)


def device_cache_invalidation_handler(instance, **kwargs):
    view = DeviceChecksumView()
    setattr(view, 'kwargs', {'pk': str(instance.pk)})
    view.get_device.invalidate(view)


def config_backend_change_handler(instance, **kwargs):
    devicegroup_templates_change_handler(instance, **kwargs)


def vpn_server_change_handler(instance, **kwargs):
    transaction.on_commit(
        lambda: tasks.invalidate_vpn_server_devices_cache_change.delay(instance.id)
    )


def devicegroup_templates_change_handler(instance, **kwargs):
    if type(instance) is list:
        # instance is queryset of devices
        model_name = Device._meta.model_name
    else:
        model_name = instance._meta.model_name

    if model_name == Device._meta.model_name:
        if type(instance) is list:
            # changes group templates for multiple devices
            transaction.on_commit(
                lambda: tasks.change_devices_templates.delay(
                    instance_id=instance,
                    model_name=model_name,
                    group_id=kwargs.get('group_id'),
                    old_group_id=kwargs.get('old_group_id'),
                )
            )
        else:
            # device group changed
            transaction.on_commit(
                lambda: tasks.change_devices_templates(
                    instance_id=instance.id,
                    model_name=model_name,
                    group_id=kwargs.get('group_id'),
                    old_group_id=kwargs.get('old_group_id'),
                )
            )

    elif model_name == DeviceGroup._meta.model_name:
        # group templates changed
        transaction.on_commit(
            lambda: tasks.change_devices_templates.delay(
                instance_id=instance.id,
                model_name=model_name,
                templates=kwargs.get('templates'),
                old_templates=kwargs.get('old_templates'),
            )
        )

    elif model_name == Config._meta.model_name:
        # config created or backend changed
        config_created = instance._state.adding or (
            'created' in kwargs and kwargs['created'] is True
        )
        if not (config_created or kwargs.get('backend')):
            return
        tasks.change_devices_templates(
            instance_id=instance.id,
            model_name=model_name,
            created=config_created,
            backend=kwargs.get('backend'),
            old_backend=kwargs.get('old_backend'),
        )


def organization_disabled_handler(instance, **kwargs):
    """
    Asynchronously invalidates DeviceCheckView.get_device cache
    """
    if instance.is_active:
        return
    try:
        db_instance = Organization.objects.only('is_active').get(id=instance.id)
    except Organization.DoesNotExist:
        return
    if instance.is_active == db_instance.is_active:
        # No change in is_active
        return
    tasks.invalidate_device_checksum_view_cache.delay(str(instance.id))
