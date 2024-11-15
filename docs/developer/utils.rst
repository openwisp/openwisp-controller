Code Utilities
==============

.. include:: ../partials/developer-docs.rst

.. contents:: **Table of Contents**:
    :depth: 2
    :local:

.. _registering_unregistering_commands:

Registering / Unregistering Commands
------------------------------------

OpenWISP Controller allows to register new command options or unregister
existing command options through two utility functions:

- ``openwisp_controller.connection.commands.register_command``
- ``openwisp_controller.connection.commands.unregister_command``

You can use these functions to register new custom commands or unregister
existing commands from your code.

.. note::

    These functions are to be used as an alternative to the
    :ref:`OPENWISP_CONTROLLER_USER_COMMANDS` setting when :doc:`extending
    openwisp-controller <extending>` or when developing custom
    applications based on OpenWISP Controller.

``register_command``
~~~~~~~~~~~~~~~~~~~~

================== ==============================================
Parameter          Description
``command_name``   A ``str`` defining identifier for the command.
``command_config`` A ``dict`` like the one shown in :ref:`Command
                   Configuration: schema <comand_configuration>`.
================== ==============================================

**Note:** It will raise ``ImproperlyConfigured`` exception if a command is
already registered with the same name.

``unregister_command``
~~~~~~~~~~~~~~~~~~~~~~

================ =======================================
Parameter        Description
``command_name`` A ``str`` defining name of the command.
================ =======================================

**Note:** It will raise ``ImproperlyConfigured`` exception if such command
does not exists.

Controller Notifications
------------------------

The notification types registered and used by OpenWISP Controller are
listed in the following table.

===================== ===============================================
Notification Type     Use
``config_error``      Fires when the status of a device configuration
                      changes to ``error``.
``device_registered`` Fires when a new device registers itself.
===================== ===============================================

Registering Notification Types
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can define your own notification types using
``register_notification_type`` function from OpenWISP Notifications.

For more information, see the relevant :doc:`documentation section about
registering notification types in the Notifications module
</notifications/developer/utils>`.

Once a new notification type is registered, you can use the :doc:`"notify"
signal provided by the Notifications module
</notifications/user/sending-notifications>` to send notifications with
this new type.

Signals
-------

.. include:: /partials/signals-note.rst

``config_modified``
~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.config_modified``

**Arguments**:

- ``instance``: instance of ``Config`` which got its ``config`` modified
- ``previous_status``: indicates the status of the config object before
  the signal was emitted
- ``action``: action which emitted the signal, can be any of the list
  below: - ``config_changed``: the configuration of the config object was
  changed - ``related_template_changed``: the configuration of a related
  template was changed - ``m2m_templates_changed``: the assigned templates
  were changed (either templates were added, removed or their order was
  changed)

This signal is emitted every time the configuration of a device is
modified.

It does not matter if ``Config.status`` is already modified, this signal
will be emitted anyway because it signals that the device configuration
has changed.

This signal is used to trigger the update of the configuration on devices,
when the push feature is enabled (requires Device credentials).

The signal is also emitted when one of the templates used by the device is
modified or if the templates assigned to the device are changed.

Special cases in which ``config_modified`` is not emitted
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++

This signal is not emitted when the device is created for the first time.

It is also not emitted when templates assigned to a config object are
cleared (``post_clear`` m2m signal), this is necessary because `sortedm2m
<https://github.com/jazzband/django-sortedm2m>`_, the package we use to
implement ordered templates, uses the clear action to reorder templates
(m2m relationships are first cleared and then added back), therefore we
ignore ``post_clear`` to avoid emitting signals twice (one for the clear
action and one for the add action). Please keep this in mind if you plan
on using the clear method of the m2m manager.

``config_status_changed``
~~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.config_status_changed``

**Arguments**:

- ``instance``: instance of ``Config`` which got its ``status`` changed

This signal is emitted only when the configuration status of a device has
changed.

The signal is emitted also when the m2m template relationships of a config
object are changed, but only on ``post_add`` or ``post_remove`` actions,
``post_clear`` is ignored for the same reason explained in the previous
section.

``config_deactivating``
~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.config_deactivating``

**Arguments**:

- ``instance``: instance of the object being deactivated
- ``previous_status``: previous status of the object before deactivation

This signal is emitted when a configuration status of device is set to
``deactivating``.

``config_deactivated``
~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.config_deactivated``

**Arguments**:

- ``instance``: instance of the object being deactivated
- ``previous_status``: previous status of the object before deactivation

This signal is emitted when a configuration status of device is set to
``deactivated``.

``device_deactivated``
~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.device_deactivated``

**Arguments**:

- ``instance``: instance of the device being deactivated

This signal is emitted when a device is flagged for deactivation.

``device_activated``
~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.device_activated``

**Arguments**:

- ``instance``: instance of the device being activated

This signal is emitted when a device is flagged for activation (after
deactivation).

.. _config_backend_changed:

``config_backend_changed``
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.config_backend_changed``
**Arguments**:

- ``instance``: instance of ``Config`` which got its ``backend`` changed
- ``old_backend``: the old backend of the config object
- ``backend``: the new backend of the config object

It is not emitted when the device or config is created.

``checksum_requested``
~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.checksum_requested``

**Arguments**:

- ``instance``: instance of ``Device`` for which its configuration
  checksum has been requested
- ``request``: the HTTP request object

This signal is emitted when a device requests a checksum via the
controller views.

The signal is emitted just before a successful response is returned, it is
not sent if the response was not successful.

``config_download_requested``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.config_download_requested``

**Arguments**:

- ``instance``: instance of ``Device`` for which its configuration has
  been requested for download
- ``request``: the HTTP request object

This signal is emitted when a device requests to download its
configuration via the controller views.

The signal is emitted just before a successful response is returned, it is
not sent if the response was not successful.

``is_working_changed``
~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.connection.signals.is_working_changed``

**Arguments**:

- ``instance``: instance of ``DeviceConnection``
- ``is_working``: value of ``DeviceConnection.is_working``
- ``old_is_working``: previous value of ``DeviceConnection.is_working``,
  either ``None`` (for new connections), ``True`` or ``False``
- ``failure_reason``: error message explaining reason for failure in
  establishing connection
- ``old_failure_reason``: previous value of
  ``DeviceConnection.failure_reason``

This signal is emitted every time ``DeviceConnection.is_working`` changes.

It is not triggered when the device is created for the first time.

``management_ip_changed``
~~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.management_ip_changed``

**Arguments**:

- ``instance``: instance of ``Device``
- ``management_ip``: value of ``Device.management_ip``
- ``old_management_ip``: previous value of ``Device.management_ip``

This signal is emitted every time ``Device.management_ip`` changes.

It is not triggered when the device is created for the first time.

``device_registered``
~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.device_registered``

**Arguments**:

- ``instance``: instance of ``Device`` which got registered.
- ``is_new``: boolean, will be ``True`` when the device is new, ``False``
  when the device already exists (e.g.: a device which gets a factory
  reset will register again)

This signal is emitted when a device registers automatically through the
controller HTTP API.

``device_name_changed``
~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.device_name_changed``

**Arguments**:

- ``instance``: instance of ``Device``.

The signal is emitted when the device name changes.

It is not emitted when the device is created.

``device_group_changed``
~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.device_group_changed``

**Arguments**:

- ``instance``: instance of ``Device``.
- ``group_id``: primary key of ``DeviceGroup`` of ``Device``
- ``old_group_id``: primary key of previous ``DeviceGroup`` of ``Device``

The signal is emitted when the device group changes.

It is not emitted when the device is created.

.. _group_templates_changed:

``group_templates_changed``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.group_templates_changed``

**Arguments**:

- ``instance``: instance of ``DeviceGroup``.
- ``templates``: list of ``Template`` objects assigned to ``DeviceGroup``
- ``old_templates``: list of ``Template`` objects assigned earlier to
  ``DeviceGroup``

The signal is emitted when the device group templates changes.

It is not emitted when the device is created.

``subnet_provisioned``
~~~~~~~~~~~~~~~~~~~~~~

**Path**:
``openwisp_controller.subnet_division.signals.subnet_provisioned``

**Arguments**:

- ``instance``: instance of ``VpnClient``.
- ``provisioned``: dictionary of ``Subnet`` and ``IpAddress`` provisioned,
  ``None`` if nothing is provisioned

The signal is emitted when subnets and IP addresses have been provisioned
for a ``VpnClient`` for a VPN server with a subnet with :doc:`subnet
division rule <../user/subnet-division-rules>`.

``vpn_server_modified``
~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.vpn_server_modified``

**Arguments**:

- ``instance``: instance of ``Vpn``.

The signal is emitted when the VPN server is modified.

``vpn_peers_changed``
~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.vpn_peers_changed``

**Arguments**:

- ``instance``: instance of ``Vpn``.

The signal is emitted when the peers of VPN server gets changed.

It is only emitted for ``Vpn`` object with **WireGuard** or **VXLAN over
WireGuard** backend.
