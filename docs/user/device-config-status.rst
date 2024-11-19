Device Configuration Status
===========================

The device's configuration status (`Device.config.status`) indicates the
current state of the configuration as managed by OpenWISP. The possible
statuses and their meanings are outlined below:

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
the device to revert to its previous configuration to prevent errors.

``deactivating``
----------------

The device is in the process of being deactivated. The configuration is
scheduled to be removed from the device.

``deactivated``
---------------

The device has been deactivated. Its configuration has been completely
removed, and it is no longer managed by OpenWISP.
