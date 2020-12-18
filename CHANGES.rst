Changelog
=========

Version 0.8.3 [2020-12-18]
--------------------------

Bugfixes
~~~~~~~~

- Increased minimum `openwisp-users version to ~=0.5.1
  <https://github.com/openwisp/openwisp-users/blob/master/CHANGES.rst#version-051-2020-12-13>`_,
  which fixes an `issue in the production setup <https://github.com/openwisp/ansible-openwisp2/issues/233>`_

Version 0.8.2 [2020-12-11]
--------------------------

Bugfixes
~~~~~~~~

- Fixed the `bug <https://github.com/openwisp/openwisp-controller/issues/334>`_
  that prevented users from adding/editing access credentials.

Changes
~~~~~~~

- Increased `django-x509 <https://github.com/openwisp/django-x509#django-x509>`_
  version to 0.9.2
- Increased `django-flat-json-widget <https://github.com/openwisp/django-flat-json-widget#django-flat-json-widget>`_
  version to 0.1.2
- Changed the `preview` button colors for better readability
- Added *help text* for *device name* field

Version 0.8.1 [2020-12-02]
--------------------------

Bugfixes
~~~~~~~~

- Fixed tests that were dependent on specific settings of the Django project.

Version 0.8.0 [2020-11-23]
--------------------------

Features
~~~~~~~~

- Added possibility to `extend openwisp-controller
  <https://github.com/openwisp/openwisp-controller#extending-openwisp-controller>`_
- Added flat JSON widget for configuration variables
- Added JSON Schema widget to credentials admin
- Added ``device_registered`` signal
- Added `OpenWISP Notifications <https://github.com/openwisp/openwisp-notifications#openwisp-notifications>`_
  module as a dependency, which brings support for
  web and email notifications for important events
- Allow using a different device model in update_config:
  his allows `OpenWISP Monitoring <https://github.com/openwisp/openwisp-monitoring#openwisp-monitoring>`_
  to override the ``can_be_updated`` method to take into account the monitoring status,
  so that push updates won't be attempted
- Added notifications for changes of ``is_working`` status of credentials
- UX, automatically add/remove default values to device context:
  automatically add or remove default values of templates to the configuration context
  (a.k.a. configuration variables) when templates are added or removed from devices
- UX: added `system defined variables
  <https://github.com/openwisp/openwisp-controller#system-defined-variables>`_ section

Changes
~~~~~~~

- **Backward incompatible**: the code of `django-netjsonconfig <https://github.com/openwisp/django-netjsonconfig>`_
  was merged in openwisp-controller to simplify maintenance
- Changed API of ``device_location`` view for consistency: ``/api/device-location/{id}/``
  becomes ``/api/v1/device/{id}/location/``, the old URL is kept for backward compatibility
  but will be removed in the future
- **Backward incompatible change**: schema url endpoint changed to ``<controller-url>/config/schema.json``
  and it's now in config namespace instead of admin namespace
- Changed VPN DH length to 2048 and move its generation to the background because it's a lot slower
- Admin: Order Device, Template and VPN alphabetically by default
- Admin: Added ``mac_address`` field to the device list page (``DeviceAdmin.list_display``)
- Increased ``max_length`` of common name to ``64``
- Changed the config apply logic to avoid restarting the openwisp-config
  deamon if the configuration apply procedure is already being run
- Made template ``config`` field required in most cases
- Changed ``DeviceConnection.failure_reason`` field to ``TextField``,
  this avoids possible exception if ``failed_reason`` is very long,
  which may happen in some corner cases
- Made Device ``verbose_name`` configurable, see ``OPENWISP_CONTROLLER_DEVICE_VERBOSE_NAME``
- Increased `netjsonconfig <https://github.com/openwisp/netjsonconfig#netjsonconfig>`__ version to 0.9.x
  (which brings support for new interface types,
  `see the change log of netjsonconfig <http://netjsonconfig.openwisp.org/en/latest/general/changelog.html#version-0-9-0-2020-11-18>`_
  for more information)
- Increased `django-x509 <https://github.com/openwisp/django-x509#django-x509>`_ version to 0.9.x
- Increased `django-loci <https://github.com/openwisp/django-loci#django-loci>`_ version to 0.4.x
  (which brings many bug fixes to the mapping feature, as long as support for
  geo-coding and reverse geo-coding,
  `see the change log of django-loci <https://github.com/openwisp/django-loci/blob/master/CHANGES.rst#version-040-2020-11-19>`_
  for more information)
- Increased `openwisp-users <https://github.com/openwisp/openwisp-users#openwisp-users>`__ version from 0.2.x to 0.5.x
  (which brings many interesting improvements to multi-tenancy,
  `see the change log of openwisp-users <https://github.com/openwisp/openwisp-users/blob/master/CHANGES.rst#version-050-2020-11-18>`_
  for more information)
- Increased `django-taggit <https://github.com/jazzband/django-taggit>`_ version to 1.3.x
- Increased `openwisp-utils <https://github.com/openwisp/openwisp-utils#openwisp-utils>`__ version to 0.7.x
- Increased `django-rest-framework-gis <https://github.com/openwisp/django-rest-framework-gis>`_ version to 0.16.x
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
  ``Config.context`` and ``Template.default_values`` must always be a dictionary,
  falsy values will be converted to empty dictionary automatically
- Fixed failures in ``update_config`` operation:
  the ``update_config`` operation will be executed only when the transaction
  is committed to the database; also handled rare but possible error conditions
- Handled device not existing case in ``update_config`` task
- Fixed auto cert feature failure when device name is too long
- UI: avoid showing main scrollbar in preview mode
- Fixed ``OPENWISP_CONTROLLER_BACKEND_DEVICE_LIST = False``
- UI fixed advanced mode bugs: positioning is done using css instead of js.
  Removed body scrollbar when in advanced mode.
  Back to normal mode with ESC key.
  Hidden netjsonconfig docs hint on narrow screens.
- Avoid simultaneous ``update_config`` tasks:
  since now the launch of the task is executed when the
  transaction is committed to the database, also the
  check for other updates in progress must be moved there
- Fixed ``OPENWISP_CONTROLLER_CONTEXT`` setting getting modified at run time
- Fixed z-index of preview overlay: the z-index is increased so it's higher
  than the main navigation menu to avoid the possibility of triggering the
  main menu inadvertently
- Prevent sending ``config_modified`` signal multiple times
- Fix timeout when changing template: slow operations are moved to the background
- Fixed variablle validation: now all the available context
  (device variables, system variables) are taken into account when performing validation
- Removed unnecessary ``static()`` call from media assets

Version 0.7.0.post1 [2020-07-01]
--------------------------------

- Increased minimum django-netjsonconfig version to 0.12

Version 0.7.0 [2020-07-01]
--------------------------

- [feature] Added signals: ``config_status_changed``, ``checksum_requested``, ``config_download_requested``
- [feature] Added the possibility of specifying default values for variables used in templates
- [feature] Added ``banner_timeout``
- [feature] Emit signal when ``DeviceConnection.is_working`` changes
- [change] **Backward incompatible change**: the ``config_modified``
  signal is not emitted anymore when the device is created
- [change] VPN files now have 0600 permissions by default
- [change] Increased minimum `netjsonconfig <https://github.com/openwisp/netjsonconfig>`_ version to 0.8.0
- [change] Increased minimum `paramiko <https://github.com/paramiko/paramiko>`_ version to 2.7.1
- [change] Increased minimum `celery <https://github.com/celery/celery/>`_ version to 4.4.3
- [fix] Avoid errors being hidden by tabs
- [fix] Fixed clashes between javascript schema validation and variables
- [fix] Fixed exception when adding device credential without type
- [fix] Fixed exception when auto adding device credentials to devices which don't have a configuration
- [fix] Avoid multiple devices having the same management IP address (multiple devices
  having the same last IP is allowed because last IP is almost always a public address)
- [docs] Documented SSH timeouts
- [docs] Update outdated steps in README instructions

Version 0.6.0 [2020-04-02]
--------------------------

- Added controller view that allows to update the device information (firmware version used)
- Recover deleted object views in recoverable objects now show latest objects first
- Added ``NETJSONCONFIG_HARDWARE_ID_AS_NAME`` setting

Version 0.5.2 [2020-03-18]
--------------------------

- [controller] Added ``NETJSONCONFIG_REGISTRATION_SELF_CREATION``
- [models] Handled accidental duplication of files across templates
- [controller] Update hardware device info during registration
  (if the device already exists, the registration will update its info)
- [admin] Moved ``hardware_id`` field in device list admin
- [bugfix] Fixed broken preview when using ``hardware_id`` context var
- [models] Flagged ``hardware_id`` as not unique (it's ``unique_together`` with ``organization``)
- [admin] Hidden device configuration context field into advanced options
- [models] Removed LEDE from the OpenWRT backend label
- [docker] Added ``REDIS_URL`` to docker-compose.yml and settings.py (for dev and test env)

Version 0.5.1 [2020-02-28]
--------------------------

- [models] Improved consistent key generation, now a consisten key is generated
  also when creating devices from the admin interface (or via model API),
  before it was only done during registration
- [admin] Fixed unsaved changes JS bug that was triggered in certain cases
- [deps] Switched back to jsonfield

Version 0.5.0 [2020-02-05]
--------------------------

- [deps] Upgraded to django 3, upgraded dependencies
- [deps] Dropped support for python 2
- [x509] Fixed serial number max length (imported from django-x509)
- [admin] Fixed bug that caused organization field to be missing
  when importing a CA or certificate

Version 0.4.0 [2020-01-09]
--------------------------

- [feature] Added connection module (possibility to SSH into devices)
- [feature] Added default operator group
- [feature] Added management IP feature
- [change] Changed configuration status: ``running`` has been renamed to ``applied``
- [admin] Added ``NETJSONCONFIG_MANAGEMENT_IP_DEVICE_LIST`` setting
- [admin] Added ``NETJSONCONFIG_BACKEND_DEVICE_LIST`` setting
- [x509] Fixed common_name redundancy
- [admin] Hidden "Download Configuration" button when no config is available
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
- [bugfix] Ensure atomicity of transactions with database during auto-registration

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

- `934be13 <https://github.com/openwisp/openwisp-controller/commit/934be13>`_:
  [models] Updated sortedm2m __str__ definition
- `b76e4e2 <https://github.com/openwisp/openwisp-controller/commit/b76e4e2>`_:
  [requirements] django-netjsonconfig>=0.6.3,<0.7.0

Version 0.2.2 [2017-07-10]
--------------------------

- `f3dc784 <https://github.com/openwisp/openwisp-controller/commit/f3dc784>`_:
  [admin] Moved ``submit_line.html`` to `openwisp-utils
  <https://github.com/openwisp/openwisp-utils>`_

Version 0.2.1 [2017-07-05]
--------------------------

- `0064b98 <https://github.com/openwisp/openwisp-controller/commit/0064b98>`_:
  [device] Added ``system`` field
- `c7fe513 <https://github.com/openwisp/openwisp-controller/commit/c7fe513>`_:
  [docs] Added "Installing for development" section to README
- `c75fa68 <https://github.com/openwisp/openwisp-controller/commit/c75fa68>`_:
  [openwisp-utils] Moved shared logic to `openwisp-utils
  <https://github.com/openwisp/openwisp-utils>`_
- `819cb21 <https://github.com/openwisp/openwisp-controller/commit/819cb21>`_:
  [requirements] django-netjsonconfig>=0.6.2,<0.7.0

Version 0.2.0 [2017-05-24]
--------------------------

- `#3 <https://github.com/openwisp/openwisp-controller/issues/3>`_:
  [feature] Added support for template tags
- `#7 <https://github.com/openwisp/openwisp-controller/issues/7>`_:
  [feature] Added ``Device`` model
- `#9 <https://github.com/openwisp/openwisp-controller/issues/9>`_:
  [admin] Load default templates JS logic only when required
- `298b2a2 <https://github.com/openwisp/openwisp-controller/commit/298b2a2>`_:
  [admin] Avoid setting ``extra_content`` to mutable object
- `d173c24 <https://github.com/openwisp/openwisp-controller/commit/d173c24>`_:
  [migrations] Squashed ``0001`` and ``0002`` to avoid postgres error
- `f5fb628 <https://github.com/openwisp/openwisp-controller/commit/f5fb628>`_:
  [migrations] Updated indexes
- `6200b7a <https://github.com/openwisp/openwisp-controller/commit/6200b7a>`_:
  [Template] Fixed ``auto_client`` bug

Version 0.1.4 [2017-04-21]
--------------------------

- `#2 <https://github.com/openwisp/openwisp-controller/issues/2>`_:
  [admin] Added templates in config filter

Version 0.1.3 [2017-03-11]
--------------------------

- `db77ae7 <https://github.com/openwisp/openwisp-controller/commit/db77ae7>`_:
  [controller] Added "error: " prefix in error responses

Version 0.1.2 [2017-03-15]
--------------------------

- `3c61053 <https://github.com/openwisp/openwisp-controller/commit/3c61053>`_:
  [admin] Ensure preview button is present
- `0087483 <https://github.com/openwisp/openwisp-controller/commit/0087483>`_:
  [models] Converted ``OrganizationConfigSettings`` to UUID primary key

Version 0.1.1 [2017-03-10]
--------------------------

- `cbca4e1 <https://github.com/openwisp/openwisp-controller/commit/cbca4e1>`_:
  [users] Fixed integration with `openwisp-users <https://github.com/openwisp/openwisp-users>`_

Version 0.1.0 [2017-03-08]
--------------------------

- added multi-tenancy (separation of organizations) to `openwisp2 <http://openwisp.org>`_
- added email confirmation of new users (via `django-allauth <http://www.intenct.nl/projects/django-allauth/>`_)
