Changelog
=========

Version 1.2.0 [Unreleased]
--------------------------

Work in progress.

Version 1.1.2 [2025-08-01]
--------------------------

Bugfixes
~~~~~~~~

- Fixed `compatibility of OpenWrt.update_config with openwisp-config >=
  1.1.0 <https://github.com/openwisp/openwisp-controller/issues/964>`__.
- Fixed `VPN-client template switch issue when switching between VPN
  servers with the same address
  <https://github.com/openwisp/openwisp-controller/issues/973>`__.
- Fixed `missing config_changed signal when reverting a template
  <https://github.com/openwisp/openwisp-controller/issues/836>`__.
- Fixed `Zerotier network name being set to "ow_zt" instead of "global"
  <https://github.com/openwisp/openwisp-controller/issues/982>`__.
- Fixed error in preview when device has no name set.
- Fixed live updates for "Send commands" when multiple websocket
  connections are open for the same device.
- Limited command results in the device admin to 30 entries to avoid
  loading issues.
- Fixed uncaught exception in ``leaflet.draw.i18n.js``.
- Fixed `handling of devices without a DeviceConnection when creating
  commands
  <https://github.com/openwisp/openwisp-controller/issues/1016>`__.
- Prevented `adding multiple VPN client templates pointing to the same VPN
  server <https://github.com/openwisp/openwisp-controller/issues/832>`__.
- Fixed timeout issues in VPN checksum and download configuration views
  for large VPN setups (e.g., 2000+ WireGuard peers) by caching the
  checksum and generated configuration.
- Fixed an issue where enforcing required templates was accidentally
  deleting `VpnClient` objects, causing them to be recreated whenever
  device templates were modified in the Django admin.
- Fixed ``HTTP 500 Server Error`` when geographic REST API endpoints
  receive a malformed resource ID.

Version 1.1.1 [2025-01-31]
--------------------------

Bugfixes
~~~~~~~~

- Fixed `recovering deleted device with related location
  <https://github.com/openwisp/openwisp-controller/issues/936>`__.
- Fixed `deleting device with “deactivating” config status
  <https://github.com/openwisp/openwisp-controller/issues/949>`__.
- Fixed `conversion of MAC address to uppercase format
  <https://github.com/openwisp/openwisp-controller/issues/922>`__ with the
  openwisp-config agent.
- Fixed `updating templates with invalid configurations to prevent
  ValidationError due to cache invalidation mechanism
  <https://github.com/openwisp/openwisp-controller/pull/948>`__.

Version 1.1.0 [2024-11-22]
--------------------------

Features
~~~~~~~~

- Added `support for ZeroTier
  <https://openwisp.io/docs/stable/controller/user/zerotier.html>`_.
- Added support for adding `configuration templates
  <https://openwisp.io/docs/stable/controller/user/device-groups.html#group-templates>`_
  and `configuration variables
  <https://openwisp.io/docs/stable/controller/user/device-groups.html#group-configuration-variables>`_
  to device groups.
- Implemented support for `SNMP credentials
  <https://openwisp.io/docs/stable/controller/user/intro.html#snmp>`_.
- Added support for device deactivation and reactivation.
- Introduced an admin action to quickly move devices between groups.
- Added autocomplete support for filters in the admin interface.
- Added support to display configuration errors reported by the OpenWISP
  config agent.
- Enabled filtering of subnets by Subnet Division Rule type.
- Allowed `limiting the number of devices per organization
  <https://openwisp.io/docs/stable/controller/user/organization-limits.html>`_.
- Added support for defining organization-level variables.
- Enabled `bulk import and export of devices
  <https://openwisp.io/docs/stable/controller/user/import-export.html>`_.
- Added `functionality to configure available commands for each
  organization
  <https://openwisp.io/docs/stable/controller/user/settings.html#openwisp-controller-organization-enabled-commands>`_.
- Added a dashboard chart showing the distribution of devices across
  different groups.
- Added filters to the REST API.

Changes
~~~~~~~

- Removing a VPN template from a device will not deleted the certificates
  associated with the ``VPNClient``. Instead, the certificates will be
  marked as revoked.
- Allowed reusing ``VNI`` across all the tunnels created using an instance
  VXLAN over WireGuard VPN.
- Added a data migration for updating ``hwmode`` configuration option of
  radio to "band". The ``hwmode`` option is deprecated on OpenWrt > 21.
- The configuration push update will not flag the configuration status as
  "applied". The status will be update once the OpenWISP Config agent on
  the device reports the status.
- Updated ``DeviceConnection.connect`` to attempt all available
  credentials.
- Changed the ``on_cascade`` property of ``BaseDeviceLocation.location``
  and ``BaseDeviceLocation.floorplan`` from ``PROTECTED`` to ``CASCADE``.
- Controller views will return ``HTTP 404`` response for devices belonging
  to disabled organizations.
- Show a loading indicator for commands in progress.
- Added VPN subnet CIDR to device's system-defined variables.
- Allowed defining subnet and IP address for VPNs with OpenVPN backend.
- Changed the target link for configuration error notifications to the
  "Configuration" tab of the device.
- JSONSchema Editor widget allows to define extra CSS classes. It will
  ignore fields with ``manual`` class.
- Increased the soft time limit for celery task that operates of bulk
  objects.
- Added notifications for background subnet division rule errors.
- Added `name` and `mac_address` to device list filters in the API.
- Use autocomplete fields for related fields.

**Dependencies**:

- Bumped ``django-sortedm2m~=4.0.0``.
- Bumped ``django-reversion~=5.1.0``.
- Bumped ``django-taggit~=4.0.0``.
- Bumped ``netjsonconfig~=1.1.0``.
- Bumped ``django-x509~=1.2.0``.
- Bumped ``django-loci~=1.1.0``.
- Bumped ``django-flat-json-widget~=0.3.0``.
- Bumped ``openwisp-users~=1.1.0``.
- Bumped ``openwisp-utils[celery]~=1.1.1``.
- Bumped ``openwisp-notifications~=1.1.0``.
- Bumped ``openwisp-ipam~=1.1.0``.
- Bumped ``djangorestframework-gis~=1.1``.
- Bumped ``paramiko[ed25519]~=3.5.0``.
- Bumped ``scp~=0.15.0``.
- Bumped ``django-cache-memoize~=0.2.0``.
- Bumped ``shortuuid~=1.0.13``.
- Bumped ``netaddr~=1.3.0``.
- Bumped ``django-import-export~=3.3.0``.
- Added support for Django ``4.1.x`` and ``4.2.x``.
- Added support for Python ``3.10``.
- Dropped support for Python ``3.7``.
- Dropped support for Django ``3.0.x`` and ``3.1.x``.

Bugfixes
~~~~~~~~

- Fixed `bug for displaying relevant templates where the backend of the
  device's configuration template does not match
  <https://github.com/openwisp/openwisp-controller/pull/771>`_.
- Fixed `displaying the command widget when the user has write permissions
  <https://github.com/openwisp/openwisp-controller/pull/854>`_.
- Fixed `DeviceConnection.get_working_connection to handle scenario where
  the device has no credentials
  <https://github.com/openwisp/openwisp-controller/pull/720>`_.
- `User need to have required model permissions to perform admin actions
  <https://github.com/openwisp/openwisp-controller/pull/873>`_.
- Fixed `import device preview table when browser is set to dark mode
  <https://github.com/openwisp/openwisp-controller/issues/851>`_.
- Fixed `subnet division rule does not allow assigning only 1 ip in /32
  <https://github.com/openwisp/openwisp-controller/issues/842>`_.
- Fixed `Device._has_group() wrongly returning True
  <https://github.com/openwisp/openwisp-controller/pull/804>`_.
- Fixed `JS of history pages on config app
  <https://github.com/openwisp/openwisp-controller/issues/681>`_.
- Fixed `REST API can creates device configs inadvertently
  <https://github.com/openwisp/openwisp-controller/issues/699>`_.
- Fixed `broken shared template preview
  <https://github.com/openwisp/openwisp-controller/issues/742>`_.
- Fixed `command APIs permissions
  <https://github.com/openwisp/openwisp-controller/issues/754>`_.
- Fixed `deleting VpnClient result in deleting all provisioned subnets of
  the device <https://github.com/openwisp/openwisp-controller/pull/805>`_.
- Fixed `group templates re-creating VPN clients
  <https://github.com/openwisp/openwisp-controller/issues/703>`_.
- Fixed `DeviceListSerializer returning HTTP 500 instead of HTTP 400
  reponse on invalid data
  <https://github.com/openwisp/openwisp-controller/issues/695>`_.
- Fixed `re-ordering applied templates in device config
  <https://github.com/openwisp/openwisp-controller/pull/830>`_.
- Fixed `re-ordering templates on device add page
  <https://github.com/openwisp/openwisp-controller/issues/434>`_.
- Fixed `several issues with clone template feature
  <https://github.com/openwisp/openwisp-controller/pull/838>`_.
- Fixed `updating template organization puts devices in perennial
  "modified" state
  <https://github.com/openwisp/openwisp-controller/issues/213>`_.
- Fixed `user defined commands that do not require input
  <https://github.com/openwisp/openwisp-controller/pull/871>`_.
- Fixed `validation for SubnetDivisionRule
  <https://github.com/openwisp/openwisp-controller/issues/706>`_.
- Fixed `subnet division rule validation when master subnet is empty
  <https://github.com/openwisp/openwisp-controller/issues/866>`_.
- Fixed `validation in change device group admin action
  <https://github.com/openwisp/openwisp-controller/issues/762>`_.
- `Increased "timeoutInterval" for ReconnectingWebSocket
  <https://github.com/openwisp/openwisp-controller/issues/772>`_.
- Added `JS workaround for using mac address variable
  <https://github.com/openwisp/openwisp-controller/pull/876>`_.
- Fixed `same credential can be added to a device twice
  <https://github.com/openwisp/openwisp-controller/issues/795>`_.
- `Show reversion button to operators too
  <https://github.com/openwisp/openwisp-controller/pull/652>`_.
- Fixed `unsaved changes alert triggering on previewing configuration
  <https://github.com/openwisp/openwisp-controller/pull/857>`_.
- Fixed `dependency on the creation date in get_max_subnet method
  <https://github.com/openwisp/openwisp-controller/issues/728>`_.
- Fixed `Vpn.webhook_endpoint accepting invalid URL
  <https://github.com/openwisp/openwisp-controller/issues/689>`_.
- Fixed `object and config menu not opening in Device config editor
  <https://github.com/openwisp/openwisp-controller/pull/913>`.

Version 1.0.3 [2022-08-03]
--------------------------

Bugfixes
~~~~~~~~

- `Fixed tests failing due to openwisp-notification>=1.0.2
  <https://github.com/openwisp/openwisp-controller/pull/670>`_
- `Fixed checksum cache is not invalidated on VPN server change
  <https://github.com/openwisp/openwisp-controller/issues/667>`_

Version 1.0.2 [2022-07-01]
--------------------------

Bugfixes
~~~~~~~~

- Fixed `device's "changed" signals emitting on the creation of new device
  <https://github.com/openwisp/openwisp-controller/issues/649>`_
- Fixed *django-reversion's* recovery buttons were hidden from users of
  the "Operator" group in the admin dashboard of ``Certificate`` and
  ``CA`` models
- Removed `hardcoded static URLs
  <https://github.com/openwisp/openwisp-controller/issues/660>`_ which
  created issues when static files are served using an external service
  (e.g. S3 storage buckets)
- Fixed `permissions for "Operator" and "Administrator" groups to access
  "OrganizationConfigSettings" objects
  <https://github.com/openwisp/openwisp-controller/issues/664>`_
- Fixed `support for multiple wireguard tunnels on the same devices
  <https://github.com/openwisp/openwisp-controller/issues/657>`_
- Fixed `"/api/v1/controller/device/{id}/" REST API endpoint not updating
  the device's configuration backend
  <https://github.com/openwisp/openwisp-controller/issues/658>`_

Version 1.0.1 [2022-05-11]
--------------------------

Bugfixes
~~~~~~~~

- Admin: show main group information in ``DeviceGroupAdmin`` list: - name
  - organization - modified - created
- Fixed uncaught exception triggered on the deletion of VPN client
  certificates
- SSH connection: fixed OpenWrt <= 19 authentication failure
- The SSH connection is now explicitly closed when the authentication
  fails to avoid leaving lingering SSH connection objects open

Version 1.0.0 [2022-04-29]
--------------------------

Features
~~~~~~~~

- Added support for `remotely executing shell commands on device
  <https://github.com/openwisp/openwisp-controller#sending-commands-to-devices>`_
- Added `automatic provisioning of Subnets and IPs
  <https://github.com/openwisp/openwisp-controller#subnet-division-app>`_
- Added `support for WireGuard and VXLAN tunnels
  <https://github.com/openwisp/openwisp-controller#how-to-setup-wireguard-tunnels>`_
- Added `required templates
  <https://github.com/openwisp/openwisp-controller#required-templates>`_
- Added support for generating configurations for OpenWrt 21
- Added `REST API
  <https://github.com/openwisp/openwisp-controller#rest-api-reference>`_
- Added dashboard charts for *config status*, *model*, *OS*, *hardware*
  and *location type*
- Added `management_ip_changed
  <https://github.com/openwisp/openwisp-controller#management_ip_changed>`_
  and `device_name_changed
  <https://github.com/openwisp/openwisp-controller#device_name_changed>`_
  signals
- Added `OPENWISP_CONTROLLER_DEVICE_NAME_UNIQUE setting
  <https://github.com/openwisp/openwisp-controller#openwisp_controller_device_name_unique>`_
  to conditionally enforce unique device names in an organization
- Added caching for ``DeviceChecksumView``
- Added support for ED25519 SSH keys in ``Credentials``
- Added `Device Groups
  <https://github.com/openwisp/openwisp-controller#device-groups>`_ to
  organize devices of a particular organization
- Configuration push updates now use the SIGUSR1 signal to reload
  openwisp-config
- The device list admin page now allows to search for location address

Changes
~~~~~~~

Backward incompatible changes
+++++++++++++++++++++++++++++

- Since django-sortedm2m, the widget we use to implement ordered
  templates, clears all the many to many relationships every time it has
  to make changes, we had to stop deleting ``VpnClient`` instances related
  to VPN templates on ``post_clear`` m2m signals If you wrote any custom
  derivative which relies on calls like
  ``device.config.templates.clear()`` to delete related ``VpnClient``
  instances and their x509 certificates, you will have to update your code
  to remove all the templates using their primary keys, instead of using
  ``clear()``
- The default behavior for the resolution of conflicting management IPs
  between devices of different organizations has been changed; by default,
  in this new version, the system assumes it's using only 1 management
  tunnel for all the organizations, so different devices from any
  organization will not have the same management IP to avoid conflicts.
  The old behaviour can be restored by setting
  `OPENWISP_CONTROLLER_SHARED_MANAGEMENT_IP_ADDRESS_SPACE
  <https://github.com/openwisp/openwisp-controller#openwisp_controller_shared_management_ip_address_space>`_
  to ``False``
- ``OPENWISP_CONTROLLER_BACKEND_DEVICE_LIST`` has been renamed to
  ``OPENWISP_CONTROLLER_CONFIG_BACKEND_FIELD_SHOWN``
- ``Device.check_management_ip_changed`` has been changed to private API
  ``Device._check_management_ip_changed``

Dependencies
++++++++++++

- Dropped support for Python 3.6
- Dropped support for Django 2.2
- Added support for Python 3.8 and 3.9
- Added support for Django 3.2 and 4.0
- Upgraded django-sortedm2m to 3.1.x
- Upgraded django-reversion to 4.0.x
- Upgraded django-taggit to 2.1.x
- Upgraded djangorestframework-gis to 0.18.0
- Upgraded paramiko[ed25519] to 2.10.3
- Upgraded scp to 0.14.2
- Upgraded django-flat-json-widget to 0.2.x
- Upgraded celery to 5.2.x
- Upgraded channels to 3.0.x
- Upgraded django-x509 to 1.1.x
- Upgraded django-loci to 1.0.x
- Upgraded netjsonconfig to 1.0.x
- Upgraded openwisp-utils to 1.0.x
- Upgraded openwisp-users to 1.0.x
- Upgraded openwisp-notifications to 1.0.x
- Upgraded openwisp-ipam to 1.0.x
- Added shortuuid 1.0.x
- Added netaddr 0.8.x
- Added django-cache-memoize to 0.1

Other changes
+++++++++++++

- `Reworked implementation of config_modified signal
  <https://github.com/openwisp/openwisp-controller#config_modified>`_:

  - the signal is now always emitted on templates changes m2m events, also
    if ``config.status`` is modified, with the differences that only
    post_add and post_remove m2m events are used, while ``post_clear`` is
    ignored, which fixes the duplicate signal emission caused by the
    implementation of sortedm2m;
  - added ``action`` and ``previous_status`` arguments, which allow to
    understand where the ``config_modified`` signal is being emitted from,
    this allows more advanced usage of the signal by custom
    implementations

- Context variable follows template order: If two or more applied
  templates have "default_values" with the same keys, then the context
  variables of the template which comes later in the order will be used
- New credentials created with ``auto_add`` set to ``True`` will get added
  to the existing devices in a background task. This improves the
  responsiveness of the web application
- Decoupled admin LogEntry from Template model
- Device admin only lists relevant templates, i.e. templates that are
  shared or belong to the device's organization
- Improved UX of `system-defined variables
  <https://github.com/openwisp/openwisp-controller/issues/344>`_
- Name of ``Vpn``, ``Template`` and ``Credentials`` objects is unique only
  within the same organization and within the shared objects
- Added functionality to configure connection failure reasons for which
  the system should not send notifications. Added ``old_failure_reason``
  parameter in
  ``openwisp_controller.connection.signals.is_working_changed`` signal
- Allowed searching devices using their location address in Device admin.
- Removed deprecated ``api/device-location/<pk>`` endpoint
- Made device name unique per organization instead of unique system wide
- Added time limits to background celery tasks

Bugfixes
~~~~~~~~

- Fixed a bug which caused ``VpnClient`` instances to be recreated every
  time the configuration templates of a device were changed, which caused
  x590 certificates to be destroyed and recreated as well
- Hardened config validation of OpenVPN backend. The validation fails if
  the ``openvpn`` key is missing from the configuration
- Fixed a bug that caused issues in updating related ``Config`` whenever a
  template's ``default_values`` were changed
- Fixed pop-up view of CA and Cert not displaying data
- Fixed config status stays ``applied`` after clearing all device
  templates
- Fixed ``VpnClient`` not created when multiple VPN templates are added
- Fixed configuration editor raising validation error when using variables
  in fields with ``maxLength`` set
- Fixed connection notifications reporting outdated status
- Fixed migrations referencing non-swappable OpenWISP modules that broke
  OpenWISP's extensibility
- Fixed bugs in restoring deleted devices using ``django-reversion``
- Fixed cloning of shared templates
- Disallowed blank values for ``key_length`` or ``digest`` fields for
  ``CA`` and ``Cert`` objects
- Fixed template ordering bug in the configuration preview on Device admin
  The order of templates was not always retained when generating the
  preview of a config object

Version 0.8.4 [2021-04-09]
--------------------------

Bugfixes
~~~~~~~~

- Fixed `bug in connection module
  <https://github.com/openwisp/openwisp-controller/issues/370>`_ that
  raised ``UnicodeDecodeError``, improved logging and ignored unicode
  conversion issues
- Fixed `context loading from default values of templates overwriting
  system defined variables
  <https://github.com/openwisp/openwisp-controller/issues/352>`_ in device
  admin
- Fixed `default template selection not updating after changing backend
  field <https://github.com/openwisp/openwisp-controller/issues/354>`_ in
  device admin
- Fixed JSONSchema widget to enable working with a single schema
- Fixed `related configuration not getting updated after template
  "default_values" are changed
  <https://github.com/openwisp/openwisp-controller/issues/352>`_
- Fixed `bug which caused the unsaved changes alert in device admin
  <https://github.com/openwisp/openwisp-controller/issues/388>`_ when
  location of device is present
- Fixed `bug replacing manually entered device information with empty
  string <https://github.com/openwisp/openwisp-controller/issues/425>`_
- Fixed `multiple requests for fetching default template values in device
  admin <https://github.com/openwisp/openwisp-controller/issues/423>`_

Security
~~~~~~~~

- Patched security bugs in internal HTTP endpoints which allowed to obtain
  UUID of other organizations and other sensitive information

Version 0.8.3 [2020-12-18]
--------------------------

Bugfixes
~~~~~~~~

- Increased minimum `openwisp-users version to ~=0.5.1
  <https://github.com/openwisp/openwisp-users/blob/master/CHANGES.rst#version-051-2020-12-13>`_,
  which fixes an `issue in the production setup
  <https://github.com/openwisp/ansible-openwisp2/issues/233>`_

Version 0.8.2 [2020-12-11]
--------------------------

Bugfixes
~~~~~~~~

- Fixed the `bug
  <https://github.com/openwisp/openwisp-controller/issues/334>`_ that
  prevented users from adding/editing access credentials.

Changes
~~~~~~~

- Increased `django-x509
  <https://github.com/openwisp/django-x509#django-x509>`_ version to 0.9.2
- Increased `django-flat-json-widget
  <https://github.com/openwisp/django-flat-json-widget#django-flat-json-widget>`_
  version to 0.1.2
- Changed the `preview` button colors for better readability
- Added *help text* for *device name* field

Version 0.8.1 [2020-12-02]
--------------------------

Bugfixes
~~~~~~~~

- Fixed tests that were dependent on specific settings of the Django
  project.

Version 0.8.0 [2020-11-23]
--------------------------

Features
~~~~~~~~

- Added possibility to `extend openwisp-controller
  <https://github.com/openwisp/openwisp-controller#extending-openwisp-controller>`_
- Added flat JSON widget for configuration variables
- Added JSON Schema widget to credentials admin
- Added ``device_registered`` signal
- Added `OpenWISP Notifications
  <https://github.com/openwisp/openwisp-notifications#openwisp-notifications>`_
  module as a dependency, which brings support for web and email
  notifications for important events
- Allow using a different device model in update_config: his allows
  `OpenWISP Monitoring
  <https://github.com/openwisp/openwisp-monitoring#openwisp-monitoring>`_
  to override the ``can_be_updated`` method to take into account the
  monitoring status, so that push updates won't be attempted
- Added notifications for changes of ``is_working`` status of credentials
- UX, automatically add/remove default values to device context:
  automatically add or remove default values of templates to the
  configuration context (a.k.a. configuration variables) when templates
  are added or removed from devices
- UX: added `system defined variables
  <https://github.com/openwisp/openwisp-controller#system-defined-variables>`_
  section

Changes
~~~~~~~

- **Backward incompatible**: the code of `django-netjsonconfig
  <https://github.com/openwisp/django-netjsonconfig>`_ was merged in
  openwisp-controller to simplify maintenance
- Changed API of ``device_location`` view for consistency:
  ``/api/device-location/{id}/`` becomes
  ``/api/v1/device/{id}/location/``, the old URL is kept for backward
  compatibility but will be removed in the future
- **Backward incompatible change**: schema url endpoint changed to
  ``<controller-url>/config/schema.json`` and it's now in config namespace
  instead of admin namespace
- Changed VPN DH length to 2048 and move its generation to the background
  because it's a lot slower
- Admin: Order Device, Template and VPN alphabetically by default
- Admin: Added ``mac_address`` field to the device list page
  (``DeviceAdmin.list_display``)
- Increased ``max_length`` of common name to ``64``
- Changed the config apply logic to avoid restarting the openwisp-config
  deamon if the configuration apply procedure is already being run
- Made template ``config`` field required in most cases
- Changed ``DeviceConnection.failure_reason`` field to ``TextField``, this
  avoids possible exception if ``failed_reason`` is very long, which may
  happen in some corner cases
- Made Device ``verbose_name`` configurable, see
  ``OPENWISP_CONTROLLER_DEVICE_VERBOSE_NAME``
- Increased `netjsonconfig
  <https://github.com/openwisp/netjsonconfig#netjsonconfig>`__ version to
  0.9.x (which brings support for new interface types, `see the change log
  of netjsonconfig
  <http://netjsonconfig.openwisp.org/en/latest/general/changelog.html#version-0-9-0-2020-11-18>`_
  for more information)
- Increased `django-x509
  <https://github.com/openwisp/django-x509#django-x509>`_ version to 0.9.x
- Increased `django-loci
  <https://github.com/openwisp/django-loci#django-loci>`_ version to 0.4.x
  (which brings many bug fixes to the mapping feature, as long as support
  for geo-coding and reverse geo-coding, `see the change log of
  django-loci
  <https://github.com/openwisp/django-loci/blob/master/CHANGES.rst#version-040-2020-11-19>`_
  for more information)
- Increased `openwisp-users
  <https://github.com/openwisp/openwisp-users#openwisp-users>`__ version
  from 0.2.x to 0.5.x (which brings many interesting improvements to
  multi-tenancy, `see the change log of openwisp-users
  <https://github.com/openwisp/openwisp-users/blob/master/CHANGES.rst#version-050-2020-11-18>`_
  for more information)
- Increased `django-taggit <https://github.com/jazzband/django-taggit>`_
  version to 1.3.x
- Increased `openwisp-utils
  <https://github.com/openwisp/openwisp-utils#openwisp-utils>`__ version
  to 0.7.x
- Increased `django-rest-framework-gis
  <https://github.com/openwisp/django-rest-framework-gis>`_ version to
  0.16.x
- Added support for django 3.1

Bugfixes
~~~~~~~~

- Fixed JSON validation error when dealing with OpenVPN configuration
- Ensured ``unique`` in ``HARDWARE_ID_OPTIONS`` defaults to ``False``
- Avoid need of migration if ``HARDWARE_ID_OPTIONS`` is changed
- JS: prevent crash if backend value is empty
- Do not execute default template selection if device exists
- Close preview overlay on errors
- Avoid triggering ``config_modified`` signal during registration
- UI: Fixed whitespace after overview tab in in device page
- Validate ``Config.context`` and ``Template.default_values``:
  ``Config.context`` and ``Template.default_values`` must always be a
  dictionary, falsy values will be converted to empty dictionary
  automatically
- Fixed failures in ``update_config`` operation: the ``update_config``
  operation will be executed only when the transaction is committed to the
  database; also handled rare but possible error conditions
- Handled device not existing case in ``update_config`` task
- Fixed auto cert feature failure when device name is too long
- UI: avoid showing main scrollbar in preview mode
- Fixed ``OPENWISP_CONTROLLER_BACKEND_DEVICE_LIST = False``
- UI fixed advanced mode bugs: positioning is done using css instead of
  js. Removed body scrollbar when in advanced mode. Back to normal mode
  with ESC key. Hidden netjsonconfig docs hint on narrow screens.
- Avoid simultaneous ``update_config`` tasks: since now the launch of the
  task is executed when the transaction is committed to the database, also
  the check for other updates in progress must be moved there
- Fixed ``OPENWISP_CONTROLLER_CONTEXT`` setting getting modified at run
  time
- Fixed z-index of preview overlay: the z-index is increased so it's
  higher than the main navigation menu to avoid the possibility of
  triggering the main menu inadvertently
- Prevent sending ``config_modified`` signal multiple times
- Fix timeout when changing template: slow operations are moved to the
  background
- Fixed variablle validation: now all the available context (device
  variables, system variables) are taken into account when performing
  validation
- Removed unnecessary ``static()`` call from media assets

Version 0.7.0.post1 [2020-07-01]
--------------------------------

- Increased minimum django-netjsonconfig version to 0.12

Version 0.7.0 [2020-07-01]
--------------------------

- [feature] Added signals: ``config_status_changed``,
  ``checksum_requested``, ``config_download_requested``
- [feature] Added the possibility of specifying default values for
  variables used in templates
- [feature] Added ``banner_timeout``
- [feature] Emit signal when ``DeviceConnection.is_working`` changes
- [change] **Backward incompatible change**: the ``config_modified``
  signal is not emitted anymore when the device is created
- [change] VPN files now have 0600 permissions by default
- [change] Increased minimum `netjsonconfig
  <https://github.com/openwisp/netjsonconfig>`_ version to 0.8.0
- [change] Increased minimum `paramiko
  <https://github.com/paramiko/paramiko>`_ version to 2.7.1
- [change] Increased minimum `celery <https://github.com/celery/celery/>`_
  version to 4.4.3
- [fix] Avoid errors being hidden by tabs
- [fix] Fixed clashes between javascript schema validation and variables
- [fix] Fixed exception when adding device credential without type
- [fix] Fixed exception when auto adding device credentials to devices
  which don't have a configuration
- [fix] Avoid multiple devices having the same management IP address
  (multiple devices having the same last IP is allowed because last IP is
  almost always a public address)
- [docs] Documented SSH timeouts
- [docs] Update outdated steps in README instructions

Version 0.6.0 [2020-04-02]
--------------------------

- Added controller view that allows to update the device information
  (firmware version used)
- Recover deleted object views in recoverable objects now show latest
  objects first
- Added ``NETJSONCONFIG_HARDWARE_ID_AS_NAME`` setting

Version 0.5.2 [2020-03-18]
--------------------------

- [controller] Added ``NETJSONCONFIG_REGISTRATION_SELF_CREATION``
- [models] Handled accidental duplication of files across templates
- [controller] Update hardware device info during registration (if the
  device already exists, the registration will update its info)
- [admin] Moved ``hardware_id`` field in device list admin
- [bugfix] Fixed broken preview when using ``hardware_id`` context var
- [models] Flagged ``hardware_id`` as not unique (it's ``unique_together``
  with ``organization``)
- [admin] Hidden device configuration context field into advanced options
- [models] Removed LEDE from the OpenWRT backend label
- [docker] Added ``REDIS_URL`` to docker-compose.yml and settings.py (for
  dev and test env)

Version 0.5.1 [2020-02-28]
--------------------------

- [models] Improved consistent key generation, now a consisten key is
  generated also when creating devices from the admin interface (or via
  model API), before it was only done during registration
- [admin] Fixed unsaved changes JS bug that was triggered in certain cases
- [deps] Switched back to jsonfield

Version 0.5.0 [2020-02-05]
--------------------------

- [deps] Upgraded to django 3, upgraded dependencies
- [deps] Dropped support for python 2
- [x509] Fixed serial number max length (imported from django-x509)
- [admin] Fixed bug that caused organization field to be missing when
  importing a CA or certificate

Version 0.4.0 [2020-01-09]
--------------------------

- [feature] Added connection module (possibility to SSH into devices)
- [feature] Added default operator group
- [feature] Added management IP feature
- [change] Changed configuration status: ``running`` has been renamed to
  ``applied``
- [admin] Added ``NETJSONCONFIG_MANAGEMENT_IP_DEVICE_LIST`` setting
- [admin] Added ``NETJSONCONFIG_BACKEND_DEVICE_LIST`` setting
- [x509] Fixed common_name redundancy
- [admin] Hidden "Download Configuration" button when no config is
  available
- [controller] Register view now updates device details
- [deps] Added support for Django 2.1 and Django 2.2
- [models] Added support for hardware ID / serial number
- [device] Add context field to device
- [bugfix] Show error when the preview is experiencing issues
- [ux] Group device change form in tabs
- [ux] Show loading indicator while loading preview
- [vpn] Add controller views (download & checksum) for VPN config
- [vpn] Fixed DH params in preview #107
- [change] Moved urls to admin namespace
- [feature] Implement copy/clone templates
- [feature] Added API to get context of device
- [bugfix] Ensure atomicity of transactions with database during
  auto-registration

Version 0.3.2 [2018-02-19]
--------------------------

- [requirements] Updated requirements and added support for django 2.0

Version 0.3.1 [2017-12-20]
--------------------------

- [pki] Reimplemented serial numbers as UUID integers
- [pki] Added switcher that facilitates importing certificates
- [pki] [admin] Removed ``serial_number`` from certificate list

Version 0.3.0 [2017-12-17]
--------------------------

- [feature] Added geographic and indoor mapping module
- [feature] Aded Dockerfile

Version 0.2.5 [2017-12-02]
--------------------------

- `#21 <https://github.com/openwisp/openwisp-controller/issues/21>`_:
  [admin] Added a link to password reset in login form

Version 0.2.4 [2017-11-07]
--------------------------

- Added support for django-x509 0.3.0

Version 0.2.3 [2017-08-29]
--------------------------

- `934be13
  <https://github.com/openwisp/openwisp-controller/commit/934be13>`_:
  [models] Updated sortedm2m __str__ definition
- `b76e4e2
  <https://github.com/openwisp/openwisp-controller/commit/b76e4e2>`_:
  [requirements] django-netjsonconfig>=0.6.3,<0.7.0

Version 0.2.2 [2017-07-10]
--------------------------

- `f3dc784
  <https://github.com/openwisp/openwisp-controller/commit/f3dc784>`_:
  [admin] Moved ``submit_line.html`` to `openwisp-utils
  <https://github.com/openwisp/openwisp-utils>`_

Version 0.2.1 [2017-07-05]
--------------------------

- `0064b98
  <https://github.com/openwisp/openwisp-controller/commit/0064b98>`_:
  [device] Added ``system`` field
- `c7fe513
  <https://github.com/openwisp/openwisp-controller/commit/c7fe513>`_:
  [docs] Added "Installing for development" section to README
- `c75fa68
  <https://github.com/openwisp/openwisp-controller/commit/c75fa68>`_:
  [openwisp-utils] Moved shared logic to `openwisp-utils
  <https://github.com/openwisp/openwisp-utils>`_
- `819cb21
  <https://github.com/openwisp/openwisp-controller/commit/819cb21>`_:
  [requirements] django-netjsonconfig>=0.6.2,<0.7.0

Version 0.2.0 [2017-05-24]
--------------------------

- `#3 <https://github.com/openwisp/openwisp-controller/issues/3>`_:
  [feature] Added support for template tags
- `#7 <https://github.com/openwisp/openwisp-controller/issues/7>`_:
  [feature] Added ``Device`` model
- `#9 <https://github.com/openwisp/openwisp-controller/issues/9>`_:
  [admin] Load default templates JS logic only when required
- `298b2a2
  <https://github.com/openwisp/openwisp-controller/commit/298b2a2>`_:
  [admin] Avoid setting ``extra_content`` to mutable object
- `d173c24
  <https://github.com/openwisp/openwisp-controller/commit/d173c24>`_:
  [migrations] Squashed ``0001`` and ``0002`` to avoid postgres error
- `f5fb628
  <https://github.com/openwisp/openwisp-controller/commit/f5fb628>`_:
  [migrations] Updated indexes
- `6200b7a
  <https://github.com/openwisp/openwisp-controller/commit/6200b7a>`_:
  [Template] Fixed ``auto_client`` bug

Version 0.1.4 [2017-04-21]
--------------------------

- `#2 <https://github.com/openwisp/openwisp-controller/issues/2>`_:
  [admin] Added templates in config filter

Version 0.1.3 [2017-03-11]
--------------------------

- `db77ae7
  <https://github.com/openwisp/openwisp-controller/commit/db77ae7>`_:
  [controller] Added "error: " prefix in error responses

Version 0.1.2 [2017-03-15]
--------------------------

- `3c61053
  <https://github.com/openwisp/openwisp-controller/commit/3c61053>`_:
  [admin] Ensure preview button is present
- `0087483
  <https://github.com/openwisp/openwisp-controller/commit/0087483>`_:
  [models] Converted ``OrganizationConfigSettings`` to UUID primary key

Version 0.1.1 [2017-03-10]
--------------------------

- `cbca4e1
  <https://github.com/openwisp/openwisp-controller/commit/cbca4e1>`_:
  [users] Fixed integration with `openwisp-users
  <https://github.com/openwisp/openwisp-users>`_

Version 0.1.0 [2017-03-08]
--------------------------

- added multi-tenancy (separation of organizations) to `openwisp2
  <http://openwisp.org>`_
- added email confirmation of new users (via `django-allauth
  <http://www.intenct.nl/projects/django-allauth/>`_)
