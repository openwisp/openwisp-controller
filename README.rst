openwisp-controller
===================

.. image:: https://github.com/openwisp/openwisp-controller/workflows/OpenWISP%20Controller%20CI%20Build/badge.svg?branch=master
   :target: https://github.com/openwisp/openwisp-controller/actions?query=workflow%3A%22OpenWISP+Controller+CI+Build%22
   :alt: CI build status

.. image:: https://coveralls.io/repos/openwisp/openwisp-controller/badge.svg
   :target: https://coveralls.io/r/openwisp/openwisp-controller
   :alt: Test Coverage

.. image:: https://requires.io/github/openwisp/openwisp-controller/requirements.svg?branch=master
   :target: https://requires.io/github/openwisp/openwisp-controller/requirements/?branch=master
   :alt: Requirements Status

.. image:: https://img.shields.io/gitter/room/nwjs/nw.js.svg
   :target: https://gitter.im/openwisp/general
   :alt: Chat

.. image:: https://badge.fury.io/py/openwisp-controller.svg
   :target: http://badge.fury.io/py/openwisp-controller
   :alt: Pypi Version

.. image:: https://pepy.tech/badge/openwisp-controller
   :target: https://pepy.tech/project/openwisp-controller
   :alt: Downloads

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://pypi.org/project/black/
   :alt: code style: black

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/master/docs/controller_demo.gif
   :target: https://github.com/openwisp/openwisp-controller/tree/master/docs/controller_demo.gif
   :alt: Feature Highlights

------------

OpenWISP Controller is a configuration manager that allows to automate several
networking tasks like adoption, provisioning, management VPN configuration,
X509 certificates automatic generation, revocation of x509 certificates and
a lot more features.

OpenWISP is not only an application designed for end users, but can also be
used as a framework on which custom network automation solutions can be built
on top of its building blocks.

Other popular building blocks that are part of the OpenWISP ecosystem are:

- `openwisp-monitoring <https://github.com/openwisp/openwisp-monitoring>`_:
  provides device status monitoring, collection of metrics, charts, alerts,
  possibility to define custom checks
- `openwisp-firmware-upgrader <https://github.com/openwisp/openwisp-firmware-upgrader>`_:
  automated firmware upgrades (single devices or mass network upgrades)
- `openwisp-radius <https://github.com/openwisp/openwisp-radius>`_:
  based on FreeRADIUS, allows to implement network access authentication systems like
  802.1x WPA2 Enterprise, captive portal authentication, Hotspot 2.0 (802.11u)
- `openwisp-network-topology <https://github.com/openwisp/openwisp-network-topology>`_:
  provides way to collect and visualize network topology data from
  dynamic mesh routing daemons or other network software (eg: OpenVPN);
  it can be used in conjunction with openwisp-monitoring to get a better idea
  of the state of the network
- `openwisp-ipam <https://github.com/openwisp/openwisp-ipam>`_:
  allows to manage the assignment of IP addresses used in the network
- `openwisp-notifications <https://github.com/openwisp/openwisp-notifications>`_:
  allows users to be aware of important events happening in the network.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp2-docs/master/assets/design/openwisp-logo-black.svg
  :target: http://openwisp.org
  :alt: OpenWISP

**Want to help OpenWISP?** `Find out how to help us grow here
<http://openwisp.io/docs/general/help-us.html>`_.

------------

.. contents:: **Table of Contents**:
   :backlinks: none
   :depth: 3

------------

Deploy it in production
-----------------------

An automated installer is available at `ansible-openwisp2 <https://github.com/openwisp/ansible-openwisp2>`_.

Dependencies
------------

* Python >= 3.6
* OpenSSL

Install stable version from pypi
--------------------------------

Install from pypi:

.. code-block:: shell

    pip install openwisp-controller

Install development version
---------------------------

Install tarball:

.. code-block:: shell

    pip install https://github.com/openwisp/openwisp-controller/tarball/master

Alternatively you can install via pip using git:

.. code-block:: shell

    pip install -e git+git://github.com/openwisp/openwisp-controller#egg=openwisp_controller

If you want to contribute, follow the instructions in
`Installing for development <#installing-for-development>`_.

Project Structure & main features
----------------------------------

OpenWISP Controller is a python package consisting of four django apps:

Config App
~~~~~~~~~~

* **configuration management** for embedded devices supporting different firmwares:
    - `OpenWRT <http://openwrt.org>`_
    - `OpenWISP Firmware <https://github.com/openwisp/OpenWISP-Firmware>`_
    - support for additional firmware can be added by `specifying custom backends <#netjsonconfig-backends>`_
* **configuration editor** based on `JSON-Schema editor <https://github.com/jdorn/json-editor>`_
* **advanced edit mode**: edit `NetJSON  <http://netjson.org>`_ *DeviceConfiguration* objects for maximum flexibility
* **configuration templates**: reduce repetition to the minimum
* `configuration variables <#how-to-use-configuration-variables>`_: reference ansible-like variables in the configuration and templates
* **template tags**: tag templates to automate different types of auto-configurations (eg: mesh, WDS, 4G)
* **device groups**: add `devices to dedicated groups <#device-groups>`_ for easy management
* **simple HTTP resources**: allow devices to automatically download configuration updates
* **VPN management**: automatically provision VPN tunnels with unique x509 certificates

PKI App
~~~~~~~

The PKI app is based on `django-x509 <https://github.com/openwisp/django-x509>`_,
it allows to create, import and view x509 CAs and certificates directly from
the administration dashboard.

Connection App
~~~~~~~~~~~~~~

This app enables the controller to instantiate connections to the devices
in order perform `push operations <#how-to-configure-push-updates>`__:

- Sending configuration updates.
- `Executing shell commands <#sending-commands-to-devices>`_.
- Perform `firmware upgrades via the additional firmware upgrade module <https://github.com/openwisp/openwisp-firmware-upgrader>`_.

The default connection protocol implemented is SSH, but other protocol
mechanism is extensible and custom protocols can be implemented as well.

Access via SSH key is recommended, the SSH key algorithms supported are:

- RSA
- Ed25519

Geo App
~~~~~~~

The geographic app is based on `django-loci <https://github.com/openwisp/django-loci>`_
and allows to define the geographic coordinates of the devices,
as well as their indoor coordinates on floorplan images.

Settings
--------

You can change the values for the following variables in
``settings.py`` to configure your instance of openwisp-controller.

``OPENWISP_SSH_AUTH_TIMEOUT``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    |   ``int``   |
+--------------+-------------+
| **default**: |    ``2``    |
+--------------+-------------+
| **unit**:    | ``seconds`` |
+--------------+-------------+

Configure timeout to wait for an authentication response when establishing a SSH connection.

``OPENWISP_SSH_BANNER_TIMEOUT``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    |   ``int``   |
+--------------+-------------+
| **default**: |    ``60``   |
+--------------+-------------+
| **unit**:    | ``seconds`` |
+--------------+-------------+

Configure timeout to wait for the banner to be presented when establishing a SSH connection.

``OPENWISP_SSH_COMMAND_TIMEOUT``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    |   ``int``   |
+--------------+-------------+
| **default**: |    ``30``   |
+--------------+-------------+
| **unit**:    | ``seconds`` |
+--------------+-------------+

Configure timeout on blocking read/write operations when executing a command in a SSH connection.

``OPENWISP_SSH_CONNECTION_TIMEOUT``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    |   ``int``   |
+--------------+-------------+
| **default**: |    ``5``    |
+--------------+-------------+
| **unit**:    | ``seconds`` |
+--------------+-------------+

Configure timeout for the TCP connect when establishing a SSH connection.

``OPENWISP_CONNECTORS``
~~~~~~~~~~~~~~~~~~~~~~~

+--------------+--------------------------------------------------------------------+
| **type**:    | ``tuple``                                                          |
+--------------+--------------------------------------------------------------------+
| **default**: | .. code-block:: python                                             |
|              |                                                                    |
|              |   (                                                                |
|              |     ('openwisp_controller.connection.connectors.ssh.Ssh', 'SSH'),  |
|              |   )                                                                |
+--------------+--------------------------------------------------------------------+

Available connector classes. Connectors are python classes that specify ways
in which OpenWISP can connect to devices in order to launch commands.

``OPENWISP_UPDATE_STRATEGIES``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+----------------------------------------------------------------------------------------+
| **type**:    | ``tuple``                                                                              |
+--------------+----------------------------------------------------------------------------------------+
| **default**: | .. code-block:: python                                                                 |
|              |                                                                                        |
|              |   (                                                                                    |
|              |     ('openwisp_controller.connection.connectors.openwrt.ssh.OpenWrt', 'OpenWRT SSH'),  |
|              |   )                                                                                    |
+--------------+----------------------------------------------------------------------------------------+

Available update strategies. An update strategy is a subclass of a
connector class which defines an ``update_config`` method which is
in charge of updating the configuration of the device.

This operation is launched in a background worker when the configuration
of a device is changed.

It's possible to write custom update strategies and add them to this
setting to make them available in OpenWISP.

``OPENWISP_CONFIG_UPDATE_MAPPING``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+--------------------------------------------------------------------+
| **type**:    | ``dict``                                                           |
+--------------+--------------------------------------------------------------------+
| **default**: | .. code-block:: python                                             |
|              |                                                                    |
|              |   {                                                                |
|              |     'netjsonconfig.OpenWrt': OPENWISP_UPDATE_STRATEGIES[0][0],     |
|              |   }                                                                |
+--------------+--------------------------------------------------------------------+

A dictionary that maps configuration backends to update strategies in order to
automatically determine the update strategy of a device connection if the
update strategy field is left blank by the user.

``OPENWISP_CONTROLLER_BACKENDS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-----------------------------------------------+
| **type**:    | ``tuple``                                     |
+--------------+-----------------------------------------------+
| **default**: | .. code-block:: python                        |
|              |                                               |
|              |   (                                           |
|              |     ('netjsonconfig.OpenWrt', 'OpenWRT'),     |
|              |     ('netjsonconfig.OpenWisp', 'OpenWISP'),   |
|              |   )                                           |
+--------------+-----------------------------------------------+

Available configuration backends. For more information, see `netjsonconfig backends
<http://netjsonconfig.openwisp.org/en/latest/general/basics.html#backend>`_.

``OPENWISP_CONTROLLER_VPN_BACKENDS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+----------------------------------------------------------------+
| **type**:    | ``tuple``                                                      |
+--------------+----------------------------------------------------------------+
| **default**: | .. code-block:: python                                         |
|              |                                                                |
|              |   (                                                            |
|              |     ('openwisp_controller.vpn_backends.OpenVpn', 'OpenVPN'),   |
|              |   )                                                            |
+--------------+----------------------------------------------------------------+

Available VPN backends for VPN Server objects. For more information, see `OpenVPN netjsonconfig backend
<http://netjsonconfig.openwisp.org/en/latest/backends/openvpn.html>`_.

A VPN backend must follow some basic rules in order to be compatible with *openwisp-controller*:

* it MUST allow at minimum and at maximum one VPN instance
* the main *NetJSON* property MUST match the lowercase version of the class name,
  eg: when using the ``OpenVpn`` backend, the system will look into
  ``config['openvpn']``
* it SHOULD focus on the server capabilities of the VPN software being used

``OPENWISP_CONTROLLER_DEFAULT_BACKEND``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+----------------------------------------+
| **type**:    | ``str``                                |
+--------------+----------------------------------------+
| **default**: | ``OPENWISP_CONTROLLER_BACKENDS[0][0]`` |
+--------------+----------------------------------------+

The preferred backend that will be used as initial value when adding new ``Config`` or
``Template`` objects in the admin.

This setting defaults to the raw value of the first item in the ``OPENWISP_CONTROLLER_BACKENDS`` setting,
which is ``netjsonconfig.OpenWrt``.

Setting it to ``None`` will force the user to choose explicitly.

``OPENWISP_CONTROLLER_DEFAULT_VPN_BACKEND``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+--------------------------------------------+
| **type**:    | ``str``                                    |
+--------------+--------------------------------------------+
| **default**: | ``OPENWISP_CONTROLLER_VPN_BACKENDS[0][0]`` |
+--------------+--------------------------------------------+

The preferred backend that will be used as initial value when adding new ``Vpn`` objects in the admin.

This setting defaults to the raw value of the first item in the ``OPENWISP_CONTROLLER_VPN_BACKENDS`` setting,
which is ``openwisp_controller.vpn_backends.OpenVpn``.

Setting it to ``None`` will force the user to choose explicitly.

``OPENWISP_CONTROLLER_REGISTRATION_ENABLED``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``bool``    |
+--------------+-------------+
| **default**: | ``True``    |
+--------------+-------------+

Whether devices can automatically register through the controller or not.

This feature is enabled by default.

Autoregistration must be supported on the devices in order to work, see `openwisp-config automatic
registration <https://github.com/openwisp/openwisp-config#automatic-registration>`_ for more information.

``OPENWISP_CONTROLLER_CONSISTENT_REGISTRATION``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``bool``    |
+--------------+-------------+
| **default**: | ``True``    |
+--------------+-------------+

Whether devices that are already registered are recognized when reflashed or reset, hence keeping
the existing configuration without creating a new one.

This feature is enabled by default.

Autoregistration must be enabled also on the devices in order to work, see `openwisp-config
consistent key generation <https://github.com/openwisp/openwisp-config#consistent-key-generation>`_
for more information.

``OPENWISP_CONTROLLER_REGISTRATION_SELF_CREATION``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``bool``    |
+--------------+-------------+
| **default**: | ``True``    |
+--------------+-------------+

Whether devices that are not already present in the system are allowed to register or not.

Turn this off if you still want to use auto-registration to avoid having to
manually set the device UUID and key in its configuration file but also want
to avoid indiscriminate registration of new devices without explicit permission.

``OPENWISP_CONTROLLER_CONTEXT``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+------------------+
| **type**:    | ``dict``         |
+--------------+------------------+
| **default**: | ``{}``           |
+--------------+------------------+

Additional context that is passed to the default context of each device object.

``OPENWISP_CONTROLLER_CONTEXT`` can be used to define system-wide configuration variables.

For more information regarding how to use configuration variables in OpenWISP,
see `How to use configuration variables <#how-to-use-configuration-variables>`_.

For technical information about how variables are handled in the lower levels
of OpenWISP, see `netjsonconfig context: configuration variables
<http://netjsonconfig.openwisp.org/en/latest/general/basics.html#context-configuration-variables>`_.

``OPENWISP_CONTROLLER_DEFAULT_AUTO_CERT``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+---------------------------+
| **type**:    | ``bool``                  |
+--------------+---------------------------+
| **default**: | ``True``                  |
+--------------+---------------------------+

The default value of the ``auto_cert`` field for new ``Template`` objects.

The ``auto_cert`` field is valid only for templates which have ``type``
set to ``VPN`` and indicates whether a new x509 certificate should be created
automatically for each configuration using that template.

The automatically created certificates will also be removed when they are not
needed anymore (eg: when the VPN template is removed from a configuration object).

``OPENWISP_CONTROLLER_CERT_PATH``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+---------------------------+
| **type**:    | ``str``                   |
+--------------+---------------------------+
| **default**: | ``/etc/x509``             |
+--------------+---------------------------+

The filesystem path where x509 certificate will be installed when
downloaded on routers when ``auto_cert`` is being used (enabled by default).

``OPENWISP_CONTROLLER_COMMON_NAME_FORMAT``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+------------------------------+
| **type**:    | ``str``                      |
+--------------+------------------------------+
| **default**: | ``{mac_address}-{name}``     |
+--------------+------------------------------+

Defines the format of the ``common_name`` attribute of VPN client certificates that are automatically
created when using VPN templates which have ``auto_cert`` set to ``True``.

``OPENWISP_CONTROLLER_MANAGEMENT_IP_DEVICE_LIST``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+------------------------------+
| **type**:    | ``bool``                     |
+--------------+------------------------------+
| **default**: | ``True``                     |
+--------------+------------------------------+

In the device list page, the column ``IP`` will show the ``management_ip`` if
available, defaulting to ``last_ip`` otherwise.

If this setting is set to ``False`` the ``management_ip`` won't be shown
in the device list page even if present, it will be shown only in the device
detail page.

You may set this to ``False`` if for some reason the majority of your user
doesn't care about the management ip address.

``OPENWISP_CONTROLLER_CONFIG_BACKEND_FIELD_SHOWN``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+------------------------------+
| **type**:    | ``bool``                     |
+--------------+------------------------------+
| **default**: | ``True``                     |
+--------------+------------------------------+

This setting toggles the ``backend`` fields in add/edit pages in Device and Template configuration,
as well as the ``backend`` field/filter in Device list and Template list.

If this setting is set to ``False`` these items will be removed from the UI.

Note: This setting affects only the configuration backend and NOT the VPN backend.

``OPENWISP_CONTROLLER_DEVICE_NAME_UNIQUE``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``bool``    |
+--------------+-------------+
| **default**: | ``True``    |
+--------------+-------------+

This setting conditionally enforces unique Device names in an Organization.
The query to enforce this is case-insensitive.

Note: For this constraint to be optional, it is enforced on an application level and not on database.

``OPENWISP_CONTROLLER_HARDWARE_ID_ENABLED``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``bool``    |
+--------------+-------------+
| **default**: | ``False``   |
+--------------+-------------+

The field ``hardware_id`` can be used to store a unique hardware id, for example a serial number.

If this setting is set to ``True`` then this field will be shown first in the device list page
and in the add/edit device page.

This feature is disabled by default.

``OPENWISP_CONTROLLER_HARDWARE_ID_OPTIONS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+--------------------------------------------------------------+
| **type**:    | ``dict``                                                     |
+--------------+--------------------------------------------------------------+
| **default**: | .. code-block:: python                                       |
|              |                                                              |
|              |    {                                                         |
|              |        'blank': not OPENWISP_CONTROLLER_HARDWARE_ID_ENABLED, |
|              |        'null': True,                                         |
|              |        'max_length': 32,                                     |
|              |        'unique': True,                                       |
|              |        'verbose_name': _('Serial number'),                   |
|              |        'help_text': _('Serial number of this device')        |
|              |    }                                                         |
+--------------+--------------------------------------------------------------+

Options for the model field ``hardware_id``.

* ``blank``: wether the field is allowed to be blank
* ``null``: wether an empty value will be stored as ``NULL`` in the database
* ``max_length``: maximum length of the field
* ``unique``: wether the value of the field must be unique
* ``verbose_name``: text for the human readable label of the field
* ``help_text``: help text to be displayed with the field

``OPENWISP_CONTROLLER_HARDWARE_ID_AS_NAME``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``bool``    |
+--------------+-------------+
| **default**: | ``True``    |
+--------------+-------------+

When the hardware ID feature is enabled, devices will be referenced with
their hardware ID instead of their name.

If you still want to reference devices by their name, set this to ``False``.

``OPENWISP_CONTROLLER_DEVICE_VERBOSE_NAME``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+----------------------------+
| **type**:    | ``tuple``                  |
+--------------+----------------------------+
| **default**: | ``('Device', 'Devices')``  |
+--------------+----------------------------+

Defines the ``verbose_name`` attribute of the ``Device`` model, which is displayed in the
admin site. The first and second element of the tuple represent the singular and plural forms.

For example, if we want to change the verbose name to "Hotspot", we could write:

.. code-block:: python

    OPENWISP_CONTROLLER_DEVICE_VERBOSE_NAME = ('Hotspot', 'Hotspots')

``OPENWISP_CONTROLLER_API``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-----------+
| **type**:    | ``bool``  |
+--------------+-----------+
| **default**: | ``True``  |
+--------------+-----------+

Indicates whether the API for Openwisp Controller is enabled or not.
To disable the API by default add `OPENWISP_CONTROLLER_API = False` in `settings.py` file.

``OPENWISP_CONTROLLER_API_HOST``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-----------+
| **type**:    | ``str``   |
+--------------+-----------+
| **default**: | ``None``  |
+--------------+-----------+

Allows to specify backend URL for API requests, if the frontend is hosted separately.

``OPENWISP_CONTROLLER_USER_COMMANDS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+----------+
| **type**:    | ``list`` |
+--------------+----------+
| **default**: | ``[]``   |
+--------------+----------+

Allows to specify a `list` of tuples for adding commands as described in
`'How to add commands" <#how-to-add-commands>`_ section.

``OPENWISP_CONTROLLER_DEVICE_GROUP_SCHEMA``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+------------------------------------------+
| **type**:    | ``dict``                                 |
+--------------+------------------------------------------+
| **default**: | ``{'type': 'object', 'properties': {}}`` |
+--------------+------------------------------------------+

Allows specifying JSONSchema used for validating meta-data of `Device Group <#device-groups>`_.

REST API
--------

Live documentation
~~~~~~~~~~~~~~~~~~

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/master/docs/live-docu-api.png

A general live API documentation (following the OpenAPI specification) at ``/api/v1/docs/``.

Browsable web interface
~~~~~~~~~~~~~~~~~~~~~~~

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/master/docs/browsable-api-ui.png

Additionally, opening any of the endpoints `listed below <#list-of-endpoints>`_
directly in the browser will show the `browsable API interface of Django-REST-Framework
<https://www.django-rest-framework.org/topics/browsable-api/>`_,
which makes it even easier to find out the details of each endpoint.

Authentication
~~~~~~~~~~~~~~

See openwisp-users: `authenticating with the user token
<https://github.com/openwisp/openwisp-users#authenticating-with-the-user-token>`_.

When browsing the API via the `Live documentation <#live-documentation>`_
or the `Browsable web page <#browsable-web-interface>`_, you can also use
the session authentication by logging in the django admin.

Pagination
~~~~~~~~~~

All *list* endpoints support the ``page_size`` parameter that allows paginating
the results in conjunction with the ``page`` parameter.

.. code-block:: text

    GET /api/v1/controller/template/?page_size=10
    GET /api/v1/controller/template/?page_size=10&page=2

List of endpoints
~~~~~~~~~~~~~~~~~

Since the detailed explanation is contained in the `Live documentation <#live-documentation>`_
and in the `Browsable web page <#browsable-web-interface>`_ of each point,
here we'll provide just a list of the available endpoints,
for further information please open the URL of the endpoint in your browser.

List devices
^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/device/

Create device
^^^^^^^^^^^^^

.. code-block:: text

    POST /api/v1/controller/device/

Get device detail
^^^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/device/{id}/

Download device configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/device/{id}/configuration/

The above endpoint triggers the download of a ``tar.gz`` file containing the generated configuration for that specific device.

Change details of device
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    PUT /api/v1/controller/device/{id}/

Patch details of device
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    PATCH /api/v1/controller/device/{id}/

**Note**: To assign, unassign, and change the order of the assigned templates add,
remove, and change the order of the ``{id}`` of the templates under the ``config`` field in the JSON response respectively.
Moreover, you can also select and unselect templates in the HTML Form of the Browsable API.

The required template(s) from the organization(s) of the device will added automatically
to the ``config`` and cannot be removed.

**Example usage**: For assigning template(s) add the/their {id} to the config of a device,

.. code-block:: shell

    echo '{"config":{"templates": ["4791fa4c-2cef-4f42-8bb4-c86018d71bd3"]}}' | \
    http PATCH http://127.0.0.1:8000/api/v1/controller/device/76b7d9cc-4ffd-4a43-b1b0-8f8befd1a7c0/ \
    "Authorization: Bearer 9b5e40da02d107cfdb9d6b69b26dc00332ec2fbc"

**Example usage**: For removing assigned templates, simply remove the/their {id} from the config of a device,

.. code-block:: shell

    echo '{"config":{"templates": []}}' | \
    http PATCH http://127.0.0.1:8000/api/v1/controller/device/76b7d9cc-4ffd-4a43-b1b0-8f8befd1a7c0/ \
    "Authorization: Bearer 9b5e40da02d107cfdb9d6b69b26dc00332ec2fbc"

**Example usage**: For reordering the templates simply change their order from the config of a device,

.. code-block:: shell

    echo '{"config":{"templates": ["c5bbc697-170e-44bc-8eb7-b944b55ee88f","4791fa4c-2cef-4f42-8bb4-c86018d71bd3"]}}' | \
    http PATCH http://127.0.0.1:8000/api/v1/controller/device/76b7d9cc-4ffd-4a43-b1b0-8f8befd1a7c0/ \
    "Authorization: Bearer 9b5e40da02d107cfdb9d6b69b26dc00332ec2fbc"

Delete device
^^^^^^^^^^^^^

.. code-block:: text

    DELETE /api/v1/controller/device/{id}/

List device connections
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/device/{id}/connection/

Create device connection
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    POST /api/v1/controller/device/{id}/connection/

Get device connection detail
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/device/{id}/connection/{id}/

Change device connection detail
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    PUT /api/v1/controller/device/{id}/connection/{id}/

Patch device connection detail
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    PATCH /api/v1/controller/device/{id}/connection/{id}/

Delete device connection
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    DELETE /api/v1/controller/device/{id}/connection/{id}/

List credentials
^^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/connection/credential/

Create credential
^^^^^^^^^^^^^^^^^

.. code-block:: text

    POST /api/v1/connection/credential/

Get credential detail
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/connection/credential/{id}/

Change credential detail
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    PUT /api/v1/connection/credential/{id}/

Patch credential detail
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    PATCH /api/v1/connection/credential/{id}/

Delete credential
^^^^^^^^^^^^^^^^^

.. code-block:: text

    DELETE /api/v1/connection/credential/{id}/

List commands of a device
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/device/{id}/command/

Execute a command a device
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    POST /api/v1/controller/device/{id}/command/

Get command details
^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/device/{device_id}/command/{command_id}/

Get device coordinates
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/device/{id}/location/

Update device coordinates
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    PUT /api/v1/controller/device/{id}/location/

List of devices in a location
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: text

    GET /api/v1/controller/location/{id}/device/

List locations with devices deployed (in GeoJSON format)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: text

    GET /api/v1/controller/location/geojson/

You can filter using ``organization_slug`` to list location of
devices from that organization

.. code:: text

    GET /api/v1/controller/location/geojson/?organization_slug=<organization_slug>

List device groups
^^^^^^^^^^^^^^^^^^

.. code:: text

    GET api/v1/controller/group/

Create device group
^^^^^^^^^^^^^^^^^^^

.. code:: text

    POST api/v1/controller/group/

Get device group detail
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/group/{id}/

Get device group from certificate common name
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/cert/{common_name}/group/

This endpoint can be used to retrieve group information and metadata by the
common name of a certificate used in a VPN client tunnel, this endpoint is
used in layer 2 tunneling solutions for firewall/captive portals.

It is also possible to filter device group by providing organization slug
of certificate's organization as show in the example below:

.. code-block:: text

    GET /api/v1/controller/cert/{common_name}/group/?org={org1_slug},{org2_slug}

List templates
^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/template/

Create template
^^^^^^^^^^^^^^^

.. code-block:: text

    POST /api/v1/controller/template/

Get template detail
^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/template/{id}/

Download template configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/template/{id}/configuration/

The above endpoint triggers the download of a ``tar.gz`` file
containing the generated configuration for that specific template.

Change details of template
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    PUT /api/v1/controller/template/{id}/

Patch details of template
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    PATCH /api/v1/controller/template/{id}/

Delete template
^^^^^^^^^^^^^^^

.. code-block:: text

    DELETE /api/v1/controller/template/{id}/

List VPNs
^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/vpn/

Create VPN
^^^^^^^^^^

.. code-block:: text

    POST /api/v1/controller/vpn/

Get VPN detail
^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/vpn/{id}/

Download VPN configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/vpn/{id}/configuration/

The above endpoint triggers the download of a ``tar.gz`` file
containing the generated configuration for that specific VPN.

Change details of VPN
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    PUT /api/v1/controller/vpn/{id}/

Patch details of VPN
^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    PATCH /api/v1/controller/vpn/{id}/

Delete VPN
^^^^^^^^^^

.. code-block:: text

    DELETE /api/v1/controller/vpn/{id}/

List CA
^^^^^^^

.. code-block:: text

    GET /api/v1/controller/ca/

Create new CA
^^^^^^^^^^^^^

.. code-block:: text

    POST /api/v1/controller/ca/

Import existing CA
^^^^^^^^^^^^^^^^^^

.. code-block:: text

    POST /api/v1/controller/ca/

**Note**: To import an existing CA, only ``name``, ``certificate``
and ``private_key`` fields have to be filled in the ``HTML`` form or
included in the ``JSON`` format.

Get CA Detail
^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/ca/{id}/

Change details of CA
^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    PUT /api/v1/controller/ca/{id}/

Patch details of CA
^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    PATCH /api/v1/controller/ca/{id}/

Download CA(crl)
^^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/ca/{id}/crl/

The above endpoint triggers the download of ``{id}.crl`` file containing
up to date CRL of that specific CA.

Delete CA
^^^^^^^^^

.. code-block:: text

    DELETE /api/v1/controller/ca/{id}/

Renew CA
^^^^^^^^

.. code-block:: text

    POST /api/v1/controller/ca/{id}/renew/

List Cert
^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/cert/

Create new Cert
^^^^^^^^^^^^^^^

.. code-block:: text

    POST /api/v1/controller/cert/

Import existing Cert
^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    POST /api/v1/controller/cert/

**Note**: To import an existing Cert, only ``name``, ``ca``,
``certificate`` and ``private_key`` fields have to be filled
in the ``HTML`` form or included in the ``JSON`` format.

Get Cert Detail
^^^^^^^^^^^^^^^

.. code-block:: text

    GET /api/v1/controller/cert/{id}/

Change details of Cert
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    PUT /api/v1/controller/cert/{id}/

Patch details of Cert
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    PATCH /api/v1/controller/cert/{id}/

Delete Cert
^^^^^^^^^^^

.. code-block:: text

    DELETE /api/v1/controller/cert/{id}/

Renew Cert
^^^^^^^^^^

.. code-block:: text

    POST /api/v1/controller/cert/{id}/renew/

Revoke Cert
^^^^^^^^^^^

.. code-block:: text

    POST /api/v1/controller/cert/{id}/revoke/

Default Alerts / Notifications
------------------------------

+-----------------------+---------------------------------------------------------------------+
| Notification Type     | Use                                                                 |
+-----------------------+---------------------------------------------------------------------+
| ``config_error``      | Fires when status of a device configuration changes to  ``error``.  |
+-----------------------+---------------------------------------------------------------------+
| ``device_registered`` | Fires when a new device is registered automatically on the network. |
+-----------------------+---------------------------------------------------------------------+

Installing for development
--------------------------

Install the system dependencies:

.. code-block:: shell

    sudo apt install -y sqlite3 libsqlite3-dev openssl libssl-dev
    sudo apt install -y gdal-bin libproj-dev libgeos-dev libspatialite-dev libsqlite3-mod-spatialite
    sudo snap install chromium

Fork and clone the forked repository:

.. code-block:: shell

    git clone git://github.com/<your_fork>/openwisp-controller

Navigate into the cloned repository:

.. code-block:: shell

    cd openwisp-controller/

Launch Redis:

.. code-block:: shell

    docker-compose up -d redis

Setup and activate a virtual-environment. (we'll be using  `virtualenv <https://pypi.org/project/virtualenv/>`_)

.. code-block:: shell

    python -m virtualenv env
    source env/bin/activate

Make sure that you are using pip version 20.2.4 before moving to the next step:

.. code-block:: shell

    pip install -U "pip==20.2.4" wheel setuptools


Install development dependencies:

.. code-block:: shell

    pip install -e .
    pip install -r requirements-test.txt
    npm install -g jshint stylelint

Install WebDriver for Chromium for your browser version from `<https://chromedriver.chromium.org/home>`_
and Extract ``chromedriver`` to one of directories from your ``$PATH`` (example: ``~/.local/bin/``).

Create database:

.. code-block:: shell

    cd tests/
    ./manage.py migrate
    ./manage.py createsuperuser

Launch celery worker (for background jobs):

.. code-block:: shell

    celery -A openwisp2 worker -l info

Launch development server:

.. code-block:: shell

    ./manage.py runserver 0.0.0.0:8000

You can access the admin interface at http://127.0.0.1:8000/admin/.

Run tests with:

.. code-block:: shell

    ./runtests.py --parallel

Run quality assurance tests with:

.. code-block:: shell

    ./run-qa-checks

Install and run on docker
--------------------------

NOTE: This Docker image is for development purposes only.
For the official OpenWISP Docker images, see: `docker-openwisp
<https://github.com/openwisp/docker-openwisp>`_.

Build from the Dockerfile:

.. code-block:: shell

    docker-compose build

Run the docker container:

.. code-block:: shell

    docker-compose up

Troubleshooting Steps
---------------------

You may encounter some issues while installing GeoDjango.

Unable to load SpatiaLite library extension?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are getting below exception::

   django.core.exceptions.ImproperlyConfigured: Unable to load the SpatiaLite library extension

then, You need to specify ``SPATIALITE_LIBRARY_PATH`` in your ``settings.py`` as explained in
`django documentation regarding how to install and configure spatialte
<https://docs.djangoproject.com/en/2.1/ref/contrib/gis/install/spatialite/>`_.

Having Issues with other geospatial libraries?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Please refer
`troubleshooting issues related to geospatial libraries
<https://docs.djangoproject.com/en/2.1/ref/contrib/gis/install/#library-environment-settings/>`_.

Device Groups
-------------

Device Groups provide an easy way to organize devices of a particular organization.
You can achieve following by using Device Groups:

- Group similar devices by having dedicated groups for access points, routers, etc.
- Store additional information regarding a group in the structured metadata field.
- Customize structure and validation of metadata field of DeviceGroup to standardize
  information across all groups using `"OPENWISP_CONTROLLER_DEVICE_GROUP_SCHEMA" <#openwisp-controller-device-group-schema>`_
  setting.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/master/docs/device-groups.png
  :alt: Device Group example

How to use configuration variables
----------------------------------

Sometimes the configuration is not exactly equal on all the devices,
some parameters are unique to each device or need to be changed
by the user.

In these cases it is possible to use configuration variables in conjunction
with templates, this feature is also known as *configuration context*, think of
it like a dictionary which is passed to the function which renders the
configuration, so that it can fill variables according to the passed context.

The different ways in which variables are defined are described below.

Predefined device variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each device gets the following attributes passed as configuration variables:

* ``id``
* ``key``
* ``name``
* ``mac_address``

User defined device variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the device configuration section you can find a section named
"Configuration variables" where it is possible to define the configuration
variables and their values, as shown in the example below:

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/master/docs/device-context.png
   :alt: context

Template default values
~~~~~~~~~~~~~~~~~~~~~~~

It's possible to specify the default values of variables defined in a template.

This allows to achieve 2 goals:

1. pass schema validation without errors (otherwise it would not be possible
   to save the template in the first place)
2. provide good default values that are valid in most cases but can be
   overridden in the device if needed

These default values will be overridden by the
`User defined device variables <#user-defined-device-variables>`_.

The default values of variables can be manipulated from the section
"configuration variables" in the edit template page:

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/master/docs/template-default-values.png
  :alt: default values

Global variables
~~~~~~~~~~~~~~~~

Variables can also be defined globally using the
`OPENWISP_CONTROLLER_CONTEXT <#openwisp-controller-context>`_ setting.

System defined variables
~~~~~~~~~~~~~~~~~~~~~~~~

Predefined device variables, global variables and other variables that
are automatically managed by the system (eg: when using templates of
type VPN-client) are displayed in the admin UI as *System Defined Variables*
in read-only mode.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/master/docs/system-defined-variables.png
   :alt: system defined variables

Example usage of variables
~~~~~~~~~~~~~~~~~~~~~~~~~~

Here's a typical use case, the WiFi SSID and WiFi password.
You don't want to define this for every device, but you may want to
allow operators to easily change the SSID or WiFi password for a
specific device without having to re-define the whole wifi interface
to avoid duplicating information.

This would be the template:

.. code-block:: json

    {
        "interfaces": [
            {
                "type": "wireless",
                "name": "wlan0",
                "wireless": {
                    "mode": "access_point",
                    "radio": "radio0",
                    "ssid": "{{wlan0_ssid}}",
                    "encryption": {
                        "protocol": "wpa2_personal",
                        "key": "{{wlan0_password}}",
                        "cipher": "auto"
                    }
                }
            }
        ]
    }

These would be the default values in the template:

.. code-block:: json

    {
        "wlan0_ssid": "SnakeOil PublicWiFi",
        "wlan0_password": "Snakeoil_pwd!321654"
    }

The default values can then be overridden at
`device level <#user-defined-device-variables>`_ if needed, eg:

.. code-block:: json

    {
        "wlan0_ssid": "Room 23 ACME Hotel",
        "wlan0_password": "room_23pwd!321654"
    }

How to configure push updates
-----------------------------

Follow the procedure described below to enable secure SSH access from OpenWISP to your
devices, this is required to enable push updates (whenever the configuration is changed,
OpenWISP will trigger the update in the background) and/or
`firmware upgrades (via the additional module openwisp-firmware-upgrader)
<https://github.com/openwisp/openwisp-firmware-upgrader>`_.

**Note**: If you have installed OpenWISP with `openwisp2 Ansbile role <https://galaxy.ansible.com/openwisp/openwisp2>`_
then you can skip the following steps. The Ansible role automatically creates a
default template to update ``authorized_keys`` on networking devices using the
default access credentials.

1. Generate SSH key
~~~~~~~~~~~~~~~~~~~

First of all, we need to generate the SSH key which will be
used by OpenWISP to access the devices, to do so, you can use the following command:

.. code-block:: shell

    echo './sshkey' | ssh-keygen -t rsa -b 4096 -C "openwisp"

This will create two files in the current directory, one called ``sshkey`` (the private key) and one called
``sshkey.pub`` (the public key).

Store the content of these files in a secure location.

2. Save SSH private key in OpenWISP (access credentials)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/master/docs/add-ssh-credentials-private-key.png
  :alt: add SSH private key as access credential in OpenWISP

From the first page of OpenWISP click on "Access credentials", then click
on the **"ADD ACCESS CREDENTIALS"** button in the upper right corner
(alternatively, go to the following URL: ``/admin/connection/credentials/add/``).

Select SSH as ``type``, enable the **Auto add** checkbox, then at the field
"Credentials type" select "SSH (private key)", now type "root" in the ``username`` field,
while in the ``key`` field you have to paste the contents of the private key just created.

Now hit save.

The credentials just created will be automatically enabled for all the devices in the system
(both existing devices and devices which will be added in the future).

3. Add the public key to your devices
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/master/docs/add-authorized-ssh-keys-template.png
  :alt: Add authorized SSH public keys template to OpenWISP (OpenWRT)

Now we need to instruct your devices to allow OpenWISP accessing via SSH,
in order to do this we need to add the contents of the public key file created in step 1
(``sshkey.pub``) in the file ``/etc/dropbear/authorized_keys`` on the devices, the
recommended way to do this is to create a configuration template in OpenWISP:
from the first page of OpenWISP, click on "Templates", then and click on the
**"ADD TEMPLATE"** button in the upper right corner (alternatively, go to the following URL:
``/admin/config/template/add/``).

Check **enabled by default**, then scroll down the configuration section,
click on "Configuration Menu", scroll down, click on "Files" then close the menu
by clicking again on "Configuration Menu". Now type ``/etc/dropbear/authorized_keys``
in the ``path`` field of the file, then paste the contents of ``sshkey.pub`` in ``contents``.

Now hit save.

**There's a catch**: you will need to assign the template to any existing device.

4. Test it
~~~~~~~~~~

Once you have performed the 3 steps above, you can test it as follows:

1. Ensure there's at least one device turned on and connected to OpenWISP, ensure
   this device has the "SSH Authorized Keys" assigned to it.
2. Ensure the celery worker of OpenWISP Controller is running (eg: ``ps aux | grep celery``)
3. SSH into the device and wait (maximum 2 minutes) until ``/etc/dropbear/authorized_keys``
   appears as specified in the template.
4. While connected via SSH to the device run the following command in the console:
   ``logread -f``, now try changing the device name in OpenWISP
5. Shortly after you change the name in OpenWISP, you should see some output in the
   SSH console indicating another SSH access and the configuration update being performed.

Sending Commands to Devices
---------------------------

By default, there are three options in the **Send Command** dropdown:

1. Reboot
2. Change Password
3. Custom Command

While the first two options are self-explanatory, the **custom command** option
allows you to execute any command on the device as shown in the example below.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/commands_demo.gif
   :target: https://github.com/openwisp/openwisp-controller/tree/docs/docs/commands_demo.gif
   :alt: Executing commands on device example

**Note**: in order for this feature to work, a device needs to have at least
one **Access Credential** (see `How to configure push updates <#how-to-configure-push-updates>`__).

The **Send Command** button will be hidden until the device
has at least one **Access Credential**.

If you need to allow your users to quickly send specific commands that are used often in your
network regardless of your users' knowledge of Linux shell commands, you can add new commands
by following instructions in `"How to add commands" <#how-to-add-commands>`_ section.

If you are an advanced user and want to register commands programatically, then refer to
`"Register / Unregistering commands" <#registering--unregistering-commands>`_ section.

How to add commands
~~~~~~~~~~~~~~~~~~~

This example introduces a simple command that could ``ping`` an input
``destination_address`` through an interface, ``interface_name``.

.. code-block:: python

    # In yourproject/settings.py

    def ping_command_callable(destination_address, interface_name=None):
        command = f'ping -c 4 {destination_address}'
        if interface_name:
            command += f' -I {interface_name}'
        return command

    OPENWISP_CONTROLLER_USER_COMMANDS = [
        (
            'ping',
            {
                'label': 'Ping',
                'schema': {
                    'title': 'Ping',
                    'type': 'object',
                    'required': ['destination_address'],
                    'properties': {
                        'destination_address': {
                            'type': 'string',
                            'title': 'Destination Address',
                        },
                        'interface_name': {
                            'type': 'string',
                            'title': 'Interface Name',
                        },
                    },
                    'message': 'Destination Address cannot be empty',
                    'additionalProperties': False,
                },
                'callable': ping_command_callable,
            }
        )
    ]

The above code will add "Ping" command as show in the GIF below:

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/ping_command_example.gif
   :target: https://github.com/openwisp/openwisp-controller/tree/docs/docs/ping_command_example.gif
   :alt: Adding a "ping" command

``OPENWISP_CONTROLLER_USER_COMMANDS`` setting takes a ``list`` of ``tuple``
each containing two elements. The first element of the tuple should contain an
identifier for the command and the second element should contain a ``dict``
defining configuration of the command.

Command Configuration
^^^^^^^^^^^^^^^^^^^^^

The ``dict`` defining configuration for command should contain following keys:

1. ``label``
""""""""""""

A ``str`` defining label for the command used internally by Django.

2. ``schema``
"""""""""""""

A ``dict`` defining `JSONSchema <https://json-schema.org/>`_ for inputs of command.
You can specify the inputs for your command, add rules for performing validation
and make inputs required or optional.

Here is a detailed explanation of the schema used in above example:

.. code-block:: python

    {
        # Name of the command displayed in "Send Command" widget
        'title': 'Ping',
        # Use type "object" if the command needs to accept inputs
        # Use type "null" if the command does not accepts any input
        'type': 'object',
        # Specify list of inputs that are required
        'required': ['destination_address'],
        # Define the inputs for the commands along with their properties
        'properties': {
            'destination_address': {
                # type of the input value
                'type': 'string',
                # label used for displaying this input field
                'title': 'Destination Address',
            },
            'interface_name': {
                'type': 'string',
                'title': 'Interface Name',
            },
        },
        # Error message to be shown if validation fails
        'message': 'Destination Address cannot be empty'),
        # Whether specifying addtionaly inputs is allowed from the input form
        'additionalProperties': False,
    }

This example uses only handful of properties available in JSONSchema. You can
experiment with other properties of JSONSchema for schema of your command.

3. ``callable``
"""""""""""""""

A ``callable`` or ``str`` defining dotted path to a callable. It should return
the command (``str``) to be executed on the device. Inputs of the command are
passed as arguments to this callable.

The example above includes a callable(``ping_command_callable``) for
``ping`` command.

Registering / Unregistering Commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

OpenWISP Controller provides registering and unregistering commands
through utility functions ``openwisp_controller.connection.commands.register_command``
and ``openwisp_notifications.types.unregister_notification_type``.
Using these functions you can register or unregister commands from your code.

**Note**: These functions are to be used as an alternative to the
`"OPENWISP_CONTROLLER_USER_COMMANDS" <#openwisp-controller-user-commands>`_ when
`developing custom modules based on openwisp-controller <#extending-openwisp-controller>`_

``register_command``
^^^^^^^^^^^^^^^^^^^^

+--------------------+------------------------------------------------------------------+
| Parameter          | Description                                                      |
+--------------------+------------------------------------------------------------------+
| ``command_name``   | A ``str`` defining identifier for the command.                   |
+--------------------+------------------------------------------------------------------+
| ``command_config`` | A ``dict`` defining configuration of the command                 |
|                    | as shown in `"Command Configuration" <#command-configuration>`_. |
+--------------------+------------------------------------------------------------------+

**Note:** It will raise ``ImproperlyConfigured`` exception if a command is already
registered with the same name.

``unregister_command``
^^^^^^^^^^^^^^^^^^^^^^

+--------------------+-----------------------------------------+
| Parameter          | Description                             |
+--------------------+-----------------------------------------+
| ``command_name``   | A ``str`` defining name of the command. |
+--------------------+-----------------------------------------+

**Note:** It will raise ``ImproperlyConfigured`` exception if such command does not exists.

Default Templates
-----------------

When templates are flagged as default, they will be automatically assigned to new devices.

If there are multiple default templates, these are assigned to the device in alphabetical
order based on their names, for example, given the following default templates:

- Access
- Interfaces
- SSH Keys

They will be assigned to devices in exactly that order.

If for some technical reason (eg: one default template depends on the presence of another
default template which must be assigned earlier) you need to change the ordering, you can
simply rename the templates by prefixing them with numbers, eg:

- 1 Interfaces
- 2. SSH Keys
- 3. Access

Required Templates
------------------

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/master/docs/required-templates.png
  :alt: Required template example

Required templates are similar to `Default templates <#default-templates>`__
but cannot be unassigned from a device configuration, they can only be overridden.

They will be always assigned earlier than default templates,
so they can be overridden if needed.

In the example above, the "SSID" template is flagged as "(required)"
and its checkbox is always checked and disabled.

Signals
-------

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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

Setup (integrate in an existing django project)
-----------------------------------------------

Add ``openwisp_controller`` applications to ``INSTALLED_APPS``:

.. code-block:: python

    INSTALLED_APPS = [
        ...
        # openwisp2 modules
        'openwisp_controller.config',
        'openwisp_controller.pki',
        'openwisp_controller.geo',
        'openwisp_controller.connection',
        'openwisp_controller.notifications',
        'openwisp_users',
        'openwisp_notifications',
        # openwisp2 admin theme
        # (must be loaded here)
        'openwisp_utils.admin_theme',
        'django.contrib.admin',
        'django.forms',
        ...
    ]
    EXTENDED_APPS = ('django_x509', 'django_loci')

**Note**: The order of applications in ``INSTALLED_APPS`` should be maintained,
otherwise it might not work properly.

Other settings needed in ``settings.py``:

.. code-block:: python

    STATICFILES_FINDERS = [
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
        'openwisp_utils.staticfiles.DependencyFinder',
    ]

    ASGI_APPLICATION = 'openwisp_controller.geo.channels.routing.channel_routing'
    CHANNEL_LAYERS = {
        # in production you should use another channel layer backend
        'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
    }

    TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'OPTIONS': {
                'loaders': [
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                    'openwisp_utils.loaders.DependencyLoader',
                ],
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                    'openwisp_utils.admin_theme.context_processor.menu_items',
                    'openwisp_notifications.context_processors.notification_api_settings',
                ],
            },
        }
    ]

    FORM_RENDERER = 'django.forms.renderers.TemplatesSetting'

Add the URLs to your main ``urls.py``:

.. code-block:: python

    urlpatterns = [
        # ... other urls in your project ...
        # openwisp-controller urls
        url(r'^admin/', admin.site.urls),
        url(r'', include('openwisp_controller.urls')),
        url(r'', include('openwisp_notifications.urls')),
    ]

Configure caching (you may use a different cache storage if you want):

.. code-block:: python

    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': 'redis://localhost/0',
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }

    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'

Configure celery (you may use a different broker if you want):

.. code-block:: python

    # here we show how to configure celery with redis but you can
    # use other brokers if you want, consult the celery docs
    CELERY_BROKER_URL = 'redis://localhost/1'

    INSTALLED_APPS.append('djcelery_email')
    EMAIL_BACKEND = 'djcelery_email.backends.CeleryEmailBackend'

If you decide to use redis (as shown in these examples),
install the requierd python packages::

    pip install redis django-redis

Then run:

.. code-block:: shell

    ./manage.py migrate

Extending openwisp-controller
-----------------------------

One of the core values of the OpenWISP project is
`Software Reusability <http://openwisp.io/docs/general/values.html#software-reusability-means-long-term-sustainability>`_,
for this reason *openwisp-controller* provides a set of base classes
which can be imported, extended and reused to create derivative apps.

In order to implement your custom version of *openwisp-controller*,
you need to perform the steps described in this section.

When in doubt, the code in the
`test project <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/>`_
will serve you as source of truth: just replicate and adapt that code
to get a basic derivative of *openwisp-controller* working.

If you want to add new users fields, please follow the `tutorial to extend the
openwisp-users <https://github.com/openwisp/openwisp-users/#extend-openwisp-users>`_.
As an example, we have extended *openwisp-users* to *sample_users* app and
added a field ``social_security_number`` in the `sample_users/models.py
<https://github.com/openwisp/openwisp-controller/blob/master/tests/openwisp2/sample_users/models.py>`_.

**Premise**: if you plan on using a customized version of this module,
we suggest to start with it since the beginning, because migrating your data
from the default module to your extended version may be time consuming.

1. Initialize your project & custom apps
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Firstly, to get started you need to create a django project::

    django-admin startproject mycontroller

Now, you need to do is to create some new django apps which will
contain your custom version of *openwisp-controller*.

A django project is a collection of django apps. There are 4 django apps in the
openwisp_controller project, namely config, pki, connection & geo.
You'll need to create 4 apps in your project for each app in openwisp_controller.

A django app is nothing more than a
`python package <https://docs.python.org/3/tutorial/modules.html#packages>`_
(a directory of python scripts), in the following examples we'll call these django app
``sample_config``, ``sample_pki``, ``sample_connection`` & ``sample_geo``
but you can name it how you want::

    django-admin startapp sample_config
    django-admin startapp sample_pki
    django-admin startapp sample_connection
    django-admin startapp sample_geo

Keep in mind that the command mentioned above must be called from a directory
which is available in your `PYTHON_PATH <https://docs.python.org/3/using/cmdline.html#envvar-PYTHONPATH>`_
so that you can then import the result into your project.

For more information about how to work with django projects and django apps,
please refer to the `django documentation <https://docs.djangoproject.com/en/dev/intro/tutorial01/>`_.

2. Install ``openwisp-controller``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install (and add to the requirement of your project) openwisp-controller::

    pip install openwisp-controller

3. Add your apps in INSTALLED_APPS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Now you need to add ``mycontroller.sample_config``,
``mycontroller.sample_pki``, ``mycontroller.sample_connection``
& ``mycontroller.sample_geo`` to ``INSTALLED_APPS`` in your ``settings.py``,
ensuring also that ``openwisp_controller.config``, ``openwisp_controller.geo``,
``openwisp_controller.pki``, ``openwisp_controller.connnection`` have been removed:

.. code-block:: python

    # Remember: Order in INSTALLED_APPS is important.
    INSTALLED_APPS = [
        # other django installed apps
        'openwisp_utils.admin_theme',
        # all-auth
        'django.contrib.sites',
        'allauth',
        'allauth.account',
        'allauth.socialaccount',
        # openwisp2 module
        # 'openwisp_controller.config', <-- comment out or delete this line
        # 'openwisp_controller.pki', <-- comment out or delete this line
        # 'openwisp_controller.geo', <-- comment out or delete this line
        # 'openwisp_controller.connection', <-- comment out or delete this line
        'mycontroller.sample_config',
        'mycontroller.sample_pki',
        'mycontroller.sample_geo',
        'mycontroller.sample_connection',
        'openwisp_users',
        # admin
        'django.contrib.admin',
        # other dependencies
        'sortedm2m',
        'reversion',
        'leaflet',
        # rest framework
        'rest_framework',
        'rest_framework_gis',
        # channels
        'channels',
    ]

Substitute ``mycontroller``, ``sample_config``, ``sample_pki``, ``sample_connection`` &
``sample_geo`` with the name you chose in step 1.

4. Add ``EXTENDED_APPS``
~~~~~~~~~~~~~~~~~~~~~~~~

Add the following to your ``settings.py``:

.. code-block:: python

    EXTENDED_APPS = (
        'django_x509',
        'django_loci',
        'openwisp_controller.config',
        'openwisp_controller.pki',
        'openwisp_controller.geo',
        'openwisp_controller.connection',
    )

5. Add ``openwisp_utils.staticfiles.DependencyFinder``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add ``openwisp_utils.staticfiles.DependencyFinder`` to
``STATICFILES_FINDERS`` in your ``settings.py``:

.. code-block:: python

    STATICFILES_FINDERS = [
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
        'openwisp_utils.staticfiles.DependencyFinder',
    ]

6. Add ``openwisp_utils.loaders.DependencyLoader``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add ``openwisp_utils.loaders.DependencyLoader`` to ``TEMPLATES``
in your ``settings.py``, but ensure it comes before
``django.template.loaders.app_directories.Loader``:

.. code-block:: python

    TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    'django.template.loaders.filesystem.Loader',
                    'openwisp_utils.loaders.DependencyLoader',
                    'django.template.loaders.app_directories.Loader',
                ],
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                    'openwisp_utils.admin_theme.context_processor.menu_items',
                    'openwisp_notifications.context_processors.notification_api_settings',
                ],
            },
        }
    ]

5. Initial Database setup
~~~~~~~~~~~~~~~~~~~~~~~~~

Ensure you are using one of the available geodjango backends, eg:

.. code-block:: python

    DATABASES = {
        'default': {
            'ENGINE': 'django.contrib.gis.db.backends.spatialite',
            'NAME': 'openwisp-controller.db',
        }
    }

For more information about GeoDjango, please refer to the `geodjango documentation <https://docs.djangoproject.com/en/dev/ref/contrib/gis/>`_.

6. Other Settings
~~~~~~~~~~~~~~~~~

Add the following settings to ``settings.py``:

.. code-block:: python

    FORM_RENDERER = 'django.forms.renderers.TemplatesSetting'

    ASGI_APPLICATION = 'openwisp_controller.geo.channels.routing.channel_routing'
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer'
        },
    }

For more information about FORM_RENDERER setting, please refer to the
`FORM_RENDERER documentation <https://docs.djangoproject.com/en/dev/ref/settings/#form-renderer>`_.
For more information about ASGI_APPLICATION setting, please refer to the
`ASGI_APPLICATION documentation <https://channels.readthedocs.io/en/latest/deploying.html#configuring-the-asgi-application>`_.
For more information about CHANNEL_LAYERS setting, please refer to the
`CHANNEL_LAYERS documentation <https://channels.readthedocs.io/en/latest/deploying.html#setting-up-a-channel-backend>`_.

6. Inherit the AppConfig class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Please refer to the following files in the sample app of the test project:

- sample_config:
    - `sample_config/__init__.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/__init__.py>`_.
    - `sample_config/apps.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/apps.py>`_.

- sample_geo:
    - `sample_geo/__init__.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/__init__.py>`_.
    - `sample_geo/apps.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/apps.py>`_.

- sample_pki:
    - `sample_pki/__init__.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_pki/__init__.py>`_.
    - `sample_pki/apps.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_pki/apps.py>`_.

- sample_connection:
    - `sample_connection/__init__.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_connection/__init__.py>`_.
    - `sample_connection/apps.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_connection/apps.py>`_.

You have to replicate and adapt that code in your project.

For more information regarding the concept of ``AppConfig`` please refer to
the `"Applications" section in the django documentation <https://docs.djangoproject.com/en/dev/ref/applications/>`_.

7. Create your custom models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For the purpose of showing an example, we added a simple "details" field
to the models of the sample app in the test project.

- `sample_config models <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/models.py>`_
- `sample_geo models <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/models.py>`_
- `sample_pki models <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_pki/models.py>`_
- `sample_connection models <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_connection/models.py>`_

You can add fields in a similar way in your ``models.py`` file.

**Note**: for doubts regarding how to use, extend or develop models please refer to
the `"Models" section in the django documentation <https://docs.djangoproject.com/en/dev/topics/db/models/>`_.

8. Add swapper configurations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you have created the models, add the following to your ``settings.py``:

.. code-block:: python

    # Setting models for swapper module
    CONFIG_DEVICE_MODEL = 'sample_config.Device'
    CONFIG_DEVICEGROUP_MODEL = 'sample_config.DeviceGroup'
    CONFIG_CONFIG_MODEL = 'sample_config.Config'
    CONFIG_TEMPLATETAG_MODEL = 'sample_config.TemplateTag'
    CONFIG_TAGGEDTEMPLATE_MODEL = 'sample_config.TaggedTemplate'
    CONFIG_TEMPLATE_MODEL = 'sample_config.Template'
    CONFIG_VPN_MODEL = 'sample_config.Vpn'
    CONFIG_VPNCLIENT_MODEL = 'sample_config.VpnClient'
    CONFIG_ORGANIZATIONCONFIGSETTINGS_MODEL = 'sample_config.OrganizationConfigSettings'
    DJANGO_X509_CA_MODEL = 'sample_pki.Ca'
    DJANGO_X509_CERT_MODEL = 'sample_pki.Cert'
    GEO_LOCATION_MODEL = 'sample_geo.Location'
    GEO_FLOORPLAN_MODEL = 'sample_geo.FloorPlan'
    GEO_DEVICELOCATION_MODEL = 'sample_geo.DeviceLocation'
    CONNECTION_CREDENTIALS_MODEL = 'sample_connection.Credentials'
    CONNECTION_DEVICECONNECTION_MODEL = 'sample_connection.DeviceConnection'
    CONNECTION_COMMAND_MODEL = 'sample_connection.Command'

Substitute ``sample_config``, ``sample_pki``, ``sample_connection`` &
``sample_geo`` with the name you chose in step 1.

9. Create database migrations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create database migrations::

    ./manage.py makemigrations

Now, to use the default ``administrator`` and ``operator`` user groups
like the used in the openwisp_controller module, you'll manually need to make a
migrations file which would look like:

- `sample_config/migrations/0002_default_groups_permissions.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/migrations/0002_default_groups_permissions.py>`_
- `sample_geo/migrations/0002_default_groups_permissions.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/migrations/0002_default_groups_permissions.py>`_
- `sample_pki/migrations/0002_default_groups_permissions.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_pki/migrations/0002_default_groups_permissions.py>`_
- `sample_connection/migrations/0002_default_groups_permissions.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_connection/migrations/0002_default_groups_permissions.py>`_

Create database migrations::

    ./manage.py migrate

For more information, refer to the
`"Migrations" section in the django documentation <https://docs.djangoproject.com/en/dev/topics/migrations/>`_.

10. Create the admin
~~~~~~~~~~~~~~~~~~~~

Refer to the ``admin.py`` file of the sample app.

- `sample_config admin.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/admin.py>`_.
- `sample_geo admin.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/admin.py>`_.
- `sample_pki admin.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_pki/admin.py>`_.
- `sample_connection admin.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_connection/admin.py>`_.

To introduce changes to the admin, you can do it in two main ways which are described below.

**Note**: for more information regarding how the django admin works, or how it can be customized,
please refer to `"The django admin site" section in the django documentation <https://docs.djangoproject.com/en/dev/ref/contrib/admin/>`_.

1. Monkey patching
^^^^^^^^^^^^^^^^^^

If the changes you need to add are relatively small, you can resort to monkey patching.

For example:

sample_config
"""""""""""""

.. code-block:: python

    from openwisp_controller.config.admin import (
        DeviceAdmin,
        DeviceGroupAdmin,
        TemplateAdmin,
        VpnAdmin,
    )

    # DeviceAdmin.fields += ['example'] <-- monkey patching example

sample_connection
"""""""""""""""""

.. code-block:: python

    from openwisp_controller.connection.admin import CredentialsAdmin

    # CredentialsAdmin.fields += ['example'] <-- monkey patching example

sample_geo
""""""""""

.. code-block:: python

    from openwisp_controller.geo.admin import FloorPlanAdmin, LocationAdmin

    # FloorPlanAdmin.fields += ['example'] <-- monkey patching example

sample_pki
""""""""""

.. code-block:: python

    from openwisp_controller.geo.admin import CaAdmin, CertAdmin

    # CaAdmin.fields += ['example'] <-- monkey patching example

2. Inheriting admin classes
^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you need to introduce significant changes and/or you don't want to resort to
monkey patching, you can proceed as follows:

sample_config
"""""""""""""

.. code-block:: python

    from django.contrib import admin
    from openwisp_controller.config.admin import (
        DeviceAdmin as BaseDeviceAdmin,
        TemplateAdmin as BaseTemplateAdmin,
        VpnAdmin as BaseVpnAdmin,
        DeviceGroupAdmin as BaseDeviceGroupAdmin,
    from swapper import load_model

    Vpn = load_model('openwisp_controller', 'Vpn')
    Device = load_model('openwisp_controller', 'Device')
    DeviceGroup = load_model('openwisp_controller', 'DeviceGroup')
    Template = load_model('openwisp_controller', 'Template')

    admin.site.unregister(Vpn)
    admin.site.unregister(Device)
    admin.site.unregister(DeviceGroup)
    admin.site.unregister(Template)

    @admin.register(Vpn)
    class VpnAdmin(BaseVpnAdmin):
        # add your changes here

    @admin.register(Device)
    class DeviceAdmin(BaseDeviceAdmin):
        # add your changes here

    @admin.register(DeviceGroup)
    class DeviceGroupAdmin(BaseDeviceGroupAdmin):
        # add your changes here

    @admin.register(Template)
    class TemplateAdmin(BaseTemplateAdmin):
        # add your changes here


sample_connection
"""""""""""""""""

.. code-block:: python

    from openwisp_controller.connection.admin import CredentialsAdmin as BaseCredentialsAdmin
    from django.contrib import admin
    from swapper import load_model

    Credentials = load_model('openwisp_controller', 'Credentials')

    admin.site.unregister(Credentials)

    @admin.register(Device)
    class CredentialsAdmin(BaseCredentialsAdmin):
        # add your changes here

sample_geo
""""""""""

.. code-block:: python

    from openwisp_controller.geo.admin import (
        FloorPlanAdmin as BaseFloorPlanAdmin,
        LocationAdmin as BaseLocationAdmin
    )
    from django.contrib import admin
    from swapper import load_model

    Location = load_model('openwisp_controller', 'Location')
    FloorPlan = load_model('openwisp_controller', 'FloorPlan')

    admin.site.unregister(FloorPlan)
    admin.site.unregister(Location)

    @admin.register(FloorPlan)
    class FloorPlanAdmin(BaseFloorPlanAdmin):
        # add your changes here

    @admin.register(Location)
    class LocationAdmin(BaseLocationAdmin):
        # add your changes here

sample_pki
""""""""""

.. code-block:: python

    from openwisp_controller.geo.admin import (
        CaAdmin as BaseCaAdmin,
        CertAdmin as BaseCertAdmin
    )
    from django.contrib import admin
    from swapper import load_model

    Ca = load_model('openwisp_controller', 'Ca')
    Cert = load_model('openwisp_controller', 'Cert')

    admin.site.unregister(Ca)
    admin.site.unregister(Cert)

    @admin.register(Ca)
    class CaAdmin(BaseCaAdmin):
        # add your changes here

    @admin.register(Cert)
    class CertAdmin(BaseCertAdmin):
        # add your changes here

11. Create root URL configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from django.contrib import admin
    from openwisp_controller.config.utils import get_controller_urls
    from openwisp_controller.geo.utils import get_geo_urls
    # from .sample_config import views as config_views
    # from .sample_geo import views as geo_views

    urlpatterns = [
        # ... other urls in your project ...
        # Use only when changing controller API views (discussed below)
        # url(r'^controller/', include((get_controller_urls(config_views), 'controller'), namespace='controller'))

        # Use only when changing geo API views (discussed below)
        # url(r'^geo/', include((get_geo_urls(geo_views), 'geo'), namespace='geo')),

        # openwisp-controller urls
        url(r'', include(('openwisp_controller.config.urls', 'config'), namespace='config')),
        url(r'', include('openwisp_controller.urls')),
    ]

For more information about URL configuration in django, please refer to the
`"URL dispatcher" section in the django documentation <https://docs.djangoproject.com/en/dev/topics/http/urls/>`_.

12. Import the automated tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When developing a custom application based on this module, it's a good
idea to import and run the base tests too, so that you can be sure the changes
you're introducing are not breaking some of the existing features of *openwisp-controller*.

In case you need to add breaking changes, you can overwrite the tests defined
in the base classes to test your own behavior.

See the tests in sample_app to find out how to do this.

- `project common tests.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/tests.py>`_
- `sample_config tests.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/tests.py>`_
- `sample_geo tests.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/tests.py>`_
- `sample_geo pytest.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/pytest.py>`_
- `sample_pki tests.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_pki/tests.py>`_
- `sample_connection tests.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_connection/tests.py>`_

For running the tests, you need to copy fixtures as well:

- Change `sample_config` to your config app's name in `sample_config fixtures <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/fixtures/>`_ and paste it in the ``sample_config/fixtures/`` directory.

You can then run tests with::

    # the --parallel flag is optional
    ./manage.py test --parallel mycontroller

Substitute ``mycontroller`` with the name you chose in step 1.

For more information about automated tests in django, please refer to
`"Testing in Django" <https://docs.djangoproject.com/en/dev/topics/testing/>`_.

Other base classes that can be inherited and extended
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following steps are not required and are intended for more advanced customization.

1. Extending the Controller API Views
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Extending the `sample_config/views.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/views.py>`_
is required only when you want to make changes in the controller API,
Remember to change ``config_views`` location in ``urls.py`` in point 11 for extending views.

For more information about django views, please refer to the `views section in the django documentation <https://docs.djangoproject.com/en/dev/topics/http/views/>`_.

2. Extending the Geo API Views
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Extending the `sample_geo/views.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/views.py>`_
is required only when you want to make changes in the geo API,
Remember to change ``geo_views`` location in ``urls.py`` in point 11 for extending views.

For more information about django views, please refer to the `views section in the django documentation <https://docs.djangoproject.com/en/dev/topics/http/views/>`_.

Registering new notification types
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can define your own notification types using ``register_notification_type`` function from OpenWISP
Notifications. For more information, see the relevant
`documentation section about registering notification types in openwisp-notifications <https://github.com/openwisp/openwisp-notifications#registering--unregistering-notification-types>`_.

Once a new notification type is registered, you have to use the `"notify" signal provided in
openwisp-notifications <https://github.com/openwisp/openwisp-notifications#sending-notifications>`_
to send notifications for this type.

Contributing
------------

Please refer to the `OpenWISP contributing guidelines <http://openwisp.io/docs/developer/contributing.html>`_.

Changelog
---------

See `CHANGES <https://github.com/openwisp/openwisp-controller/blob/master/CHANGES.rst>`_.

License
-------

See `LICENSE <https://github.com/openwisp/openwisp-controller/blob/master/LICENSE>`_.

Support
-------

See `OpenWISP Support Channels <http://openwisp.org/support.html>`_.
