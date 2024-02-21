Device Groups
-------------

Device Groups provide features aimed at adding specific management rules
for the devices of an organization:

- Group similar devices by having dedicated groups for access points, routers, etc.
- Define `group metadata <~group-metadata>`_.
- Define `group configuration templates <~group-templates>`_.
- Define `group configuration variables <~group-configuration-variables>`__.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.1/device-groups.png
  :alt: Device Group example

Group Templates
~~~~~~~~~~~~~~~

Groups allow to define templates which are automatically assigned to devices
belonging to the group. When using this feature, keep in mind the following
important points:

- Templates of any configuration backend can be selected,
  when a device is assigned to a group,
  only the templates which matches the device configuration backend are
  applied to the device.
- The system will not force group templates onto devices, this means that
  users can remove the applied group templates from a specific device if
  needed.
- If a device group is changed, the system will automatically remove the
  group templates of the old group and apply the new templates of the new
  group (this operation is implemented by leveraging the
  `group_templates_changed <~group_templates_changed>`_ signal).
- If the group templates are changed, the devices which belong to the group
  will be automatically updated to reflect the changes
  (this operation is executed in a background task).
- In case the configuration backend of a device is changed,
  the system will handle this automatically too and update the group
  templates accordingly (this operation is implemented by leveraging the
  `config_backend_changed <~config_backend_changed>`_ signal).
- If a device does not have a configuration defined yet, but it is assigned
  to a group which has templates defined, the system will automatically
  create a configuration for it using the default backend specified in
  `OPENWISP_CONTROLLER_DEFAULT_BACKEND <~OPENWISP_CONTROLLER_DEFAULT_BACKEND>`_ setting.

**Note:** the list of templates shown in the edit group page do not
contain templates flagged as ^default^ or ^required^ to avoid redundancy
because those templates are automatically assigned by the system
to new devices.

This feature works also when editing group templates or the group assigned
to a device via the `REST API <~change-device-group-detail>`__.

Group Configuration Variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Groups allow to define configuration variables which are automatically
added to the device's context in the **System Defined Variables**.
Check the `^How to use configuration variables^ section <~how-to-use-configuration-variables>`_
to learn about precedence of different configuration variables.

This feature works also when editing group templates or the group assigned
to a device via the `REST API <~change-device-group-detail>`__.

Group Metadata
~~~~~~~~~~~~~~

Groups allow to store additional information regarding a group in the
structured metadata field (which can be accessed via the REST API).

The metadata field allows custom structure and validation to standardize
information across all groups using the
`^OPENWISP_CONTROLLER_DEVICE_GROUP_SCHEMA^ <~openwisp-controller-device-group-schema>`_
setting.

**Note:** *Group configuration variables* and *Group metadata* serves different purposes.
The group configuration variables should be used when the device configuration is required
to be changed for particular group of devices. Group metadata should be used to store
additional data for the devices. Group metadata is not used for configuration generation.

Export/Import Device data
-------------------------

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.1/import-export/device-list.png
  :alt: Import / Export

The device list page offers two buttons to export and import device data in
different formats.

The export feature respects any filters selected in the device list.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.1/import-export/export-page.png
  :alt: Export

For importing devices into the system, only the required fields are needed,
for example, the following CSV file will import a device named
``TestImport`` with mac address ``00:11:22:09:44:55`` in the organization with
UUID ``3cb5e18c-0312-48ab-8dbd-038b8415bd6f``::

    organization,name,mac_address
    3cb5e18c-0312-48ab-8dbd-038b8415bd6f,TestImport,00:11:22:09:44:55

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.1/import-export/import-page.png
  :alt: Import / Export
