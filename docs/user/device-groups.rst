Device Groups
=============

Device groups allow to group similar devices together, the groups usually
share not only a common characteristic but also some kind of
organizational need: they need to have specific configuration templates,
variables and/or associated metadata which differs from the rest of the
network.

.. contents:: **Features provided by Device Groups:**
    :depth: 2
    :local:

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.1/device-groups.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.1/device-groups.png
    :alt: Device Group example

.. _device_group_templates:

Group Templates
---------------

Groups allow to define templates which are automatically assigned to
devices belonging to the group. When using this feature, keep in mind the
following important points:

- Templates of any configuration backend can be selected, when a device is
  assigned to a group, only the templates which matches the device
  configuration backend are applied to the device.
- The system will not force group templates onto devices, this means that
  users can remove the applied group templates from a specific device if
  needed.
- If a device group is changed, the system will automatically remove the
  group templates of the old group and apply the new templates of the new
  group (this operation is implemented by leveraging the
  :ref:`group_templates_changed` signal).
- If the group templates are changed, the devices which belong to the
  group will be automatically updated to reflect the changes (this
  operation is executed in a background task).
- In case the configuration backend of a device is changed, the system
  will handle this automatically too and update the group templates
  accordingly (this operation is implemented by leveraging the
  :ref:`config_backend_changed` signal).
- If a device does not have a configuration defined yet, but it is
  assigned to a group which has templates defined, the system will
  automatically create a configuration for it using the default backend
  specified in the :ref:`OPENWISP_CONTROLLER_DEFAULT_BACKEND` setting.

**Note:** the list of templates shown in the edit group page do not
contain templates flagged as :ref:`"default" <default_templates>` or
:ref:`"required" <required_templates>` to avoid redundancy because those
templates are automatically assigned by the system to new devices.

This feature works also when editing group templates or the group assigned
to a device via the :ref:`REST API <change_device_group_detail>`.

.. _device_group_variables:

Group Configuration Variables
-----------------------------

Groups allow to define configuration variables which are automatically
added to the device's context in the **System Defined Variables**. Check
the :doc:`./variables` section to learn more about precedence of different
configuration variables.

This feature also works when editing group templates or the group assigned
to a device via the :ref:`REST API <change_device_group_detail>`.

Group Metadata
--------------

Groups allow to store additional information regarding a group in the
structured metadata field (which can be accessed via the REST API).

The metadata field allows custom structure and validation to standardize
information across all groups using the
:ref:`OPENWISP_CONTROLLER_DEVICE_GROUP_SCHEMA` setting.

Variables vs Metadata
---------------------

*Group configuration variables* and *Group metadata* serves different
purposes.

The group configuration variables should be used when the device
configuration is required to be changed for particular group of devices.

Group metadata should be used to store additional data for the device
group, this data can be fetched and/or tweaked via the REST API if needed.
Group metadata is not designed to be used for configuration purposes.
