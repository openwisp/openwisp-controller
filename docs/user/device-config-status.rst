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

``deactivated``
---------------

The device has been deactivated. The configuration applied through
OpenWISP has been removed, and any other operation to manage the device
will be prevented or rejected.

.. note::

    If a device becomes unreachable (e.g., lost, stolen, or
    decommissioned) before it can be properly deactivated, you can still
    force the deletion from OpenWISP by hitting the delete button in the
    device detail page after having deactivated the device or by using the
    bulk delete action from the device list page.
