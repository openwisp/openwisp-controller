Device Configuration Status
===========================

The device's configuration status (`Device.config.status`) indicates the
current state of the configuration as managed by OpenWISP. The possible
statuses and their meanings are explained below.

``modified``
------------

The device configuration has been updated in OpenWISP, but these changes
have not yet been applied to the device. The device is pending an update.

``applied``
-----------

The device has successfully applied the configuration changes made in
OpenWISP. The current configuration on the device matches the latest
changes.

``error``
---------

An issue occurred while applying the configuration to the device, causing
the device to revert to its previous working configuration.

``deactivating``
----------------

The device is in the process of being deactivated. The configuration is
scheduled to be removed from the device.

.. _controller_deactivated_config_status:

``deactivated``
---------------

The device has been deactivated. The configuration applied through
OpenWISP has been removed, and any other operation to manage the device
will be prevented or rejected. This also includes network operations which
would normally push configuration updates, for example changes to shared
templates.

.. note::

    If a device becomes unreachable (e.g., lost, stolen, or
    decommissioned) before it can be properly deactivated, you can still
    force the deletion from OpenWISP by hitting the delete button in the
    device detail page after having deactivated the device or by using the
    bulk delete action from the device list page.

.. _controller_disabled_organization_devices:

Devices of Disabled Organizations
---------------------------------

When an organization is disabled, all its devices are deactivated
automatically: their configuration and templates are cleared and the
configuration status changes to ``deactivating`` (or directly to
``deactivated`` when there is nothing to remove).

While the organization is disabled:

- creating or changing devices and other objects of the organization is
  rejected, and devices cannot register or re-register;
- devices which are still ``deactivating`` can download their final
  configuration, receive the related push update and report their status,
  so that the removal of the configuration completes;
- VPN servers of the organization can still download their configuration
  using their key, so that the peers of the deactivated devices are
  removed;
- objects of the organization can still be viewed and deleted.
- certificates can still be revoked as a cleanup operation.

Re-enabling the organization does not reactivate its devices. Each device
must be activated again separately, for example with the "Activate" action
of the device list page.
