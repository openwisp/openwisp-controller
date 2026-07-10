from django.db import transaction
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from openwisp_notifications.signals import notify
from swapper import load_model

from . import tasks
from .signals import config_status_changed, device_registered

Config = load_model("config", "Config")
Device = load_model("config", "Device")
DeviceGroup = load_model("config", "DeviceGroup")
Organization = load_model("openwisp_users", "Organization")
Cert = load_model("django_x509", "Cert")


@receiver(
    config_status_changed,
    sender=Config,
    dispatch_uid="config_status_error_notification",
)
def config_status_error_notification(sender, instance, **kwargs):
    """
    Creates notification when status of a configuration changes to "error".
    """
    if instance.status == "error":
        notify.send(sender=instance, type="config_error", target=instance.device)


@receiver(
    device_registered, sender=Device, dispatch_uid="device_registered_notification"
)
def device_registered_notification(sender, instance, is_new, **kwargs):
    """
    Creates notification when a new device is registered automatically
    through controller.
    """
    condition = _("A new") if is_new else _("The existing")
    notify.send(
        sender=instance, type="device_registered", target=instance, condition=condition
    )


def devicegroup_change_handler(instance, **kwargs):
    """
    Manages group templates when a device's group changes.

    Cache invalidation for the device group change is handled separately
    by ``invalidate_devicegroup_cache_change_handler``, declared as a
    ``CacheDependency`` target in
    ``ConfigConfig.connect_cache_dependencies`` (see ``config/apps.py``).
    """
    if type(instance) is list:
        # changes group templates for multiple devices
        devicegroup_templates_change_handler(instance, **kwargs)
        return
    if instance._state.adding or ("created" in kwargs and kwargs["created"] is True):
        return
    # this handler is only connected to device_group_changed (sender=Device),
    # so instance is always a Device here: remove old group templates and
    # apply the new ones
    devicegroup_templates_change_handler(instance, **kwargs)


def invalidate_devicegroup_cache_change_handler(instance, **kwargs):
    """
    Invalidates the ``DeviceGroupCommonName`` cache when a device's group,
    a device group, or a certificate changes. Used as a ``CacheDependency``
    target (see ``ConfigConfig.connect_cache_dependencies`` in
    ``config/apps.py``).
    """
    if isinstance(instance, list):
        for device_id in instance:
            tasks.invalidate_devicegroup_cache_change.delay(
                device_id, Device._meta.model_name
            )
        return
    tasks.invalidate_devicegroup_cache_change.delay(
        instance.id, instance._meta.model_name
    )


def devicegroup_delete_handler(instance, **kwargs):
    """
    Invalidates the ``DeviceGroupCommonName`` cache when a device group or a
    certificate is deleted. Used as a ``CacheDependency`` target (see
    ``ConfigConfig.connect_cache_dependencies`` in ``config/apps.py``).

    Runs synchronously (the ``CacheDependency`` is declared with
    ``on_commit=False``) so it still receives the live ``instance``. Only the
    task enqueue itself is deferred to ``transaction.on_commit()``, so a
    concurrent request cannot repopulate the cache from a row that is about
    to be (or was just) deleted.

    For a deleted ``Cert``, ``common_name`` and the organization's ``slug``
    are captured here rather than looked up by the deferred task: in an
    organization-cascade delete, the ``Organization`` row itself is also
    gone by the time the task would run, so it must not depend on a
    post-commit database lookup to resolve the org's slug. A ``Cert`` can
    have no organization at all (a cert shared across organizations), in
    which case only the no-org cache entry is invalidated: ``get_device_group``
    only filters by organization when one is explicitly requested, so a
    shared cert can still populate (and needs to invalidate) that entry.
    """
    kwargs = {}
    model_name = instance._meta.model_name
    if isinstance(instance, Cert):
        if not instance.common_name:
            return
        kwargs["common_name"] = instance.common_name
        organization = instance.organization
        if organization is not None:
            kwargs["organization_slug"] = organization.slug
    else:
        kwargs["organization_id"] = instance.organization_id
    instance_id = instance.id
    transaction.on_commit(
        lambda: tasks.invalidate_devicegroup_cache_delete.delay(
            instance_id, model_name, **kwargs
        )
    )


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
                    group_id=kwargs.get("group_id"),
                    old_group_id=kwargs.get("old_group_id"),
                )
            )
        else:
            # device group changed
            transaction.on_commit(
                lambda: tasks.change_devices_templates(
                    instance_id=instance.id,
                    model_name=model_name,
                    group_id=kwargs.get("group_id"),
                    old_group_id=kwargs.get("old_group_id"),
                )
            )

    elif model_name == DeviceGroup._meta.model_name:
        # group templates changed
        transaction.on_commit(
            lambda: tasks.change_devices_templates.delay(
                instance_id=instance.id,
                model_name=model_name,
                templates=kwargs.get("templates"),
                old_templates=kwargs.get("old_templates"),
            )
        )

    elif model_name == Config._meta.model_name:
        # config created or backend changed
        config_created = instance._state.adding or (
            "created" in kwargs and kwargs["created"] is True
        )
        if not (config_created or kwargs.get("backend")):
            return
        tasks.change_devices_templates(
            instance_id=instance.id,
            model_name=model_name,
            created=config_created,
            backend=kwargs.get("backend"),
            old_backend=kwargs.get("old_backend"),
        )


def organization_disabled_handler(instance, **kwargs):
    """
    Asynchronously invalidates device and VPN controller views cache
    """
    if instance.is_active:
        return
    try:
        db_instance = Organization.objects.only("is_active").get(id=instance.id)
    except Organization.DoesNotExist:
        return
    if instance.is_active == db_instance.is_active:
        # No change in is_active
        return
    tasks.invalidate_controller_views_cache.delay(str(instance.id))
