Signals
-------

.. include:: /paritals/developers-docs-warning.rst

``config_modified``
~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.config_modified``

**Arguments**:

- ``instance``: instance of ``Config`` which got its ``config`` modified
- ``previous_status``: indicates the status of the config object before the
  signal was emitted
- ``action``: action which emitted the signal, can be any of the list below:
  - ``config_changed``: the configuration of the config object was changed
  - ``related_template_changed``: the configuration of a related template was changed
  - ``m2m_templates_changed``: the assigned templates were changed
  (either templates were added, removed or their order was changed)

This signal is emitted every time the configuration of a device is modified.

It does not matter if ``Config.status`` is already modified, this signal will
be emitted anyway because it signals that the device configuration has changed.

This signal is used to trigger the update of the configuration on devices,
when the push feature is enabled (requires Device credentials).

The signal is also emitted when one of the templates used by the device
is modified or if the templates assigned to the device are changed.

Special cases in which ``config_modified`` is not emitted
#########################################################

This signal is not emitted when the device is created for the first time.

It is also not emitted when templates assigned to a config object are
cleared (``post_clear`` m2m signal), this is necessary because
`sortedm2m <https://github.com/jazzband/django-sortedm2m>`_, the package
we use to implement ordered templates, uses the clear action to
reorder templates (m2m relationships are first cleared and then added back),
therefore we ignore ``post_clear`` to avoid emitting signals twice
(one for the clear action and one for the add action).
Please keep this in mind if you plan on using the clear method
of the m2m manager.

``config_status_changed``
~~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.config_status_changed``

**Arguments**:

- ``instance``: instance of ``Config`` which got its ``status`` changed

This signal is emitted only when the configuration status of a device has changed.

The signal is emitted also when the m2m template relationships of a config
object are changed, but only on ``post_add`` or ``post_remove`` actions,
``post_clear`` is ignored for the same reason explained
in the previous section.

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

This signal is emitted when a device requests a checksum via the controller views.

The signal is emitted just before a successful response is returned,
it is not sent if the response was not successful.

``config_download_requested``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.config.signals.config_download_requested``

**Arguments**:

- ``instance``: instance of ``Device`` for which its configuration has been
  requested for download
- ``request``: the HTTP request object

This signal is emitted when a device requests to download its configuration
via the controller views.

The signal is emitted just before a successful response is returned,
it is not sent if the response was not successful.

``is_working_changed``
~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.connection.signals.is_working_changed``

**Arguments**:

- ``instance``: instance of ``DeviceConnection``
- ``is_working``: value of ``DeviceConnection.is_working``
- ``old_is_working``: previous value of ``DeviceConnection.is_working``,
  either ``None`` (for new connections), ``True`` or ``False``
- ``failure_reason``: error message explaining reason for failure in establishing connection
- ``old_failure_reason``: previous value of ``DeviceConnection.failure_reason``

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
- ``is_new``: boolean, will be ``True`` when the device is new,
  ``False`` when the device already exists
  (eg: a device which gets a factory reset will register again)

This signal is emitted when a device registers automatically through the controller
HTTP API.

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

``group_templates_changed``
~~~~~~~~~~~~~~~~~~~~~~~~~~~


**Path**: ``openwisp_controller.config.signals.group_templates_changed``

**Arguments**:

- ``instance``: instance of ``DeviceGroup``.
- ``templates``: list of ``Template`` objects assigned to ``DeviceGroup``
- ``old_templates``: list of ``Template`` objects assigned earlier to ``DeviceGroup``

The signal is emitted when the device group templates changes.

It is not emitted when the device is created.

``subnet_provisioned``
~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_controller.subnet_division.signals.subnet_provisioned``

**Arguments**:

- ``instance``: instance of ``VpnClient``.
- ``provisioned``: dictionary of ``Subnet`` and ``IpAddress`` provisioned,
  ``None`` if nothing is provisioned

The signal is emitted when subnets and IP addresses have been provisioned
for a ``VpnClient`` for a VPN server with a subnet with
`subnet division rule <#subnet-division-app>`_.

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

It is only emitted for ``Vpn`` object with **WireGuard** or
**VXLAN over WireGuard** backend.
