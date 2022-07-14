openwisp-controller
===================

.. image:: https://github.com/openwisp/openwisp-controller/workflows/OpenWISP%20Controller%20CI%20Build/badge.svg?branch=master
   :target: https://github.com/openwisp/openwisp-controller/actions?query=workflow%3A%22OpenWISP+Controller+CI+Build%22
   :alt: CI build status

.. image:: https://coveralls.io/repos/openwisp/openwisp-controller/badge.svg
   :target: https://coveralls.io/r/openwisp/openwisp-controller
   :alt: Test Coverage

.. image:: https://img.shields.io/librariesio/release/github/openwisp/openwisp-controller
  :target: https://libraries.io/github/openwisp/openwisp-controller#repository_dependencies
  :alt: Dependency monitoring

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

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/controller_demo.gif
   :target: https://github.com/openwisp/openwisp-controller/tree/docs/docs/controller_demo.gif
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

**For a more complete overview of the OpenWISP modules and architecture**,
see the
`OpenWISP Architecture Overview
<https://openwisp.io/docs/general/architecture.html>`_.

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
* `configuration templates <https://openwisp.io/docs/user/templates.html>`_:
  reduce repetition to the minimum, configure default and required templates
* `configuration variables <#how-to-use-configuration-variables>`_:
  reference ansible-like variables in the configuration and templates
* **template tags**: tag templates to automate different types of auto-configurations (eg: mesh, WDS, 4G)
* **device groups**: add `devices to dedicated groups <#device-groups>`_ to
  ease management of group of devices
* **simple HTTP resources**: allow devices to automatically download configuration updates
* **VPN management**: `automatically provision VPN tunnels <#openwisp-controller-default-auto-cert>`_,
  including cryptographic keys, IP addresses
* `REST API <#rest-api-reference>`_

PKI App
~~~~~~~

The PKI app is based on `django-x509 <https://github.com/openwisp/django-x509>`_,
it allows to create, import and view x509 CAs and certificates directly from
the administration dashboard, it also adds different endpoints to the
`REST API <#rest-api-reference>`_.

Connection App
~~~~~~~~~~~~~~

This app enables the controller to instantiate connections to the devices
in order perform `push operations <#how-to-configure-push-updates>`__:

- Sending configuration updates.
- `Executing shell commands <#sending-commands-to-devices>`_.
- Perform `firmware upgrades via the additional firmware upgrade module <https://github.com/openwisp/openwisp-firmware-upgrader>`_.
- `REST API <#rest-api-reference>`_

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

It also adds different endpoints to the `REST API <#rest-api-reference>`_.

Subnet Division App
~~~~~~~~~~~~~~~~~~~

This app allows to automatically provision subnets and IP addresses which will be
available as `system defined configuration variables <#system-defined-variables>`_
that can be used in templates. The purpose of this app is to allow users to automatically
provision and configure specific
subnets and IP addresses to the devices without the need of manual intervention.

Refer to `"How to configure automatic provisioning of subnets and IPs"
section of this documentation
<#how-to-configure-automatic-provisioning-of-subnets-and-ips>`_
to learn about features provided by this app.

This app is optional, if you don't need it you can avoid adding it to
``settings.INSTALLED_APPS``.

Installation instructions
-------------------------

Deploy it in production
~~~~~~~~~~~~~~~~~~~~~~~

See:

- `ansible-openwisp2 <https://github.com/openwisp/ansible-openwisp2>`_
- `docker-openwisp <https://github.com/openwisp/docker-openwisp>`_

Dependencies
~~~~~~~~~~~~

* Python >= 3.7
* OpenSSL

Install stable version from pypi
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install from pypi:

.. code-block:: shell

    pip install openwisp-controller

Install development version
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install tarball:

.. code-block:: shell

    pip install https://github.com/openwisp/openwisp-controller/tarball/master

Alternatively you can install via pip using git:

.. code-block:: shell

    pip install -e git+git://github.com/openwisp/openwisp-controller#egg=openwisp_controller

If you want to contribute, follow the instructions in
`Installing for development <#installing-for-development>`_.

Installing for development
~~~~~~~~~~~~~~~~~~~~~~~~~~

Install the system dependencies:

.. code-block:: shell

    sudo apt update
    sudo apt install -y sqlite3 libsqlite3-dev openssl libssl-dev
    sudo apt install -y gdal-bin libproj-dev libgeos-dev libspatialite-dev libsqlite3-mod-spatialite
    sudo apt install -y chromium

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

    pip install -U pip wheel setuptools

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
~~~~~~~~~~~~~~~~~~~~~~~~~

NOTE: This Docker image is for development purposes only.
For the official OpenWISP Docker images, see: `docker-openwisp
<https://github.com/openwisp/docker-openwisp>`_.

Build from the Dockerfile:

.. code-block:: shell

    docker-compose build

Run the docker container:

.. code-block:: shell

    docker-compose up

Troubleshooting steps for common installation issues
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You may encounter some issues while installing GeoDjango.

Unable to load SpatiaLite library extension?
############################################

If you are getting below exception::

   django.core.exceptions.ImproperlyConfigured: Unable to load the SpatiaLite library extension

then, You need to specify ``SPATIALITE_LIBRARY_PATH`` in your ``settings.py`` as explained in
`django documentation regarding how to install and configure spatialte
<https://docs.djangoproject.com/en/2.1/ref/contrib/gis/install/spatialite/>`_.

Having Issues with other geospatial libraries?
##############################################

Please refer
`troubleshooting issues related to geospatial libraries
<https://docs.djangoproject.com/en/2.1/ref/contrib/gis/install/#library-environment-settings/>`_.

Setup (integrate in an existing django project)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add ``openwisp_controller`` applications to ``INSTALLED_APPS``:

.. code-block:: python

    INSTALLED_APPS = [
        ...
        # openwisp2 modules
        'openwisp_controller.config',
        'openwisp_controller.pki',
        'openwisp_controller.geo',
        'openwisp_controller.connection',
        'openwisp_controller.subnet_division', # Optional
        'openwisp_controller.notifications',
        'openwisp_users',
        'openwisp_notifications',
        'openwisp_ipam',
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
install the required python packages::

    pip install redis django-redis

Then run:

.. code-block:: shell

    ./manage.py migrate

Usage reference
---------------

Default Templates
~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/required-templates.png
  :alt: Required template example

Required templates are similar to `Default templates <#default-templates>`__
but cannot be unassigned from a device configuration, they can only be overridden.

They will be always assigned earlier than default templates,
so they can be overridden if needed.

In the example above, the "SSID" template is flagged as "(required)"
and its checkbox is always checked and disabled.

How to use configuration variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/device-context.png
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

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/template-default-values.png
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

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/system-defined-variables.png
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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
###################

First of all, we need to generate the SSH key which will be
used by OpenWISP to access the devices, to do so, you can use the following command:

.. code-block:: shell

    echo './sshkey' | ssh-keygen -t rsa -b 4096 -C "openwisp"

This will create two files in the current directory, one called ``sshkey`` (the private key) and one called
``sshkey.pub`` (the public key).

Store the content of these files in a secure location.

2. Save SSH private key in OpenWISP (access credentials)
########################################################

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/add-ssh-credentials-private-key.png
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
#####################################

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/add-authorized-ssh-keys-template.png
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
##########

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
by following instructions in the `"How to define new options in the commands menu"
<#how-to-define-new-options-in-the-commands-menu>`_ section below.

If you are an advanced user and want to register commands programatically, then refer to
`"Register / Unregistering commands" <#registering--unregistering-commands>`_ section.

How to define new options in the commands menu
##############################################

Let's explore to define new custom commands
to help users perform additional management actions
without having to be Linux/Unix experts.

We can do so by using the ``OPENWISP_CONTROLLER_USER_COMMANDS`` django setting.

The following example defines a simple command that can ``ping`` an input
``destination_address`` through a network interface, ``interface_name``.

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

The above code will add the "Ping" command in the user interface as show
in the GIF below:

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/ping_command_example.gif
   :target: https://github.com/openwisp/openwisp-controller/tree/docs/docs/ping_command_example.gif
   :alt: Adding a "ping" command

The ``OPENWISP_CONTROLLER_USER_COMMANDS`` setting takes a ``list`` of ``tuple``
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
####################################

OpenWISP Controller provides registering and unregistering commands
through utility functions ``openwisp_controller.connection.commands.register_command``
and ``openwisp_notifications.types.unregister_notification_type``.
You can use these functions to register or unregister commands
from your code.

**Note**: These functions are to be used as an alternative to the
`"OPENWISP_CONTROLLER_USER_COMMANDS" <#openwisp-controller-user-commands>`_
when `developing custom modules based on openwisp-controller
<#extending-openwisp-controller>`_ or when developing custom third party
apps.

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

Device Groups
~~~~~~~~~~~~~

Device Groups provide an easy way to organize devices of a particular organization.
Device Groups provide the following features:

- Group similar devices by having dedicated groups for access points, routers, etc.
- Store additional information regarding a group in the structured metadata field.
- Customize structure and validation of metadata field of DeviceGroup to standardize
  information across all groups using `"OPENWISP_CONTROLLER_DEVICE_GROUP_SCHEMA" <#openwisp-controller-device-group-schema>`_
  setting.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/device-groups.png
  :alt: Device Group example

How to setup WireGuard tunnels
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Follow the procedure described below to setup WireGuard tunnels on your devices.

**Note:** This example uses **Shared systemwide (no organization)** option as
the organization for VPN server and VPN client template. You can use any
organization as long as VPN server, VPN client template and Device has same
organization.

1. Create VPN server configuration for WireGuard
################################################

1. Visit ``/admin/config/vpn/add/`` to add a new VPN server.
2. We will set **Name** of this VPN server ``Wireguard`` and **Host** as
   ``wireguard-server.mydomain.com`` (update this to point to your
   WireGuard VPN server).
3. Select ``WireGuard`` from the dropdown as **VPN Backend**.
4. When using WireGuard, OpenWISP takes care of managing IP addresses
   (assigning an IP address to each VPN peer). You can create a new subnet or
   select an existing one from the dropdown menu. You can also assign an
   **Internal IP** to the WireGuard Server or leave it empty for OpenWISP to
   configure. This IP address will be used by the WireGuard interface on
   server.
5. We have set the **Webhook Endpoint** as ``https://wireguard-server.mydomain.com:8081/trigger-update``
   for this example. You will need to update this according to you VPN upgrader
   endpoint. Set **Webhook AuthToken** to any strong passphrase, this will be
   used to ensure that configuration upgrades are requested from trusted
   sources.

   **Note**: If you are following this tutorial for also setting up WireGuard
   VPN server, just substitute ``wireguard-server.mydomain.com`` with hostname
   of your VPN server and follow the steps in next section.

6. Under the configuration section, set the name of WireGuard tunnel 1 interface.
   We have used ``wg0`` in this example.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-tutorial/vpn-server-1.png
   :alt: WireGuard VPN server configuration example 1

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-tutorial/vpn-server-2.png
   :alt: WireGuard VPN server configuration example 2

7. After clicking on **Save and continue editing**, you will see that OpenWISP
   has automatically created public and private key for WireGuard server in
   **System Defined Variables** along with internal IP address information.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-tutorial/vpn-server-3.png
   :alt: WireGuard VPN server configuration example 3

2. Deploy Wireguard VPN Server
##############################

If you haven't already setup WireGuard on your VPN server, this will be a good
time do so. We recommend using the `ansible-wireguard-openwisp <https://github.com/openwisp/ansible-wireguard-openwisp>`_
role for installing WireGuard since it also installs scripts that allows
OpenWISP to manage WireGuard VPN server.

Pay attention to the VPN server attributes used in your playbook. It should be same as
VPN server configuration in OpenWISP.

3. Create VPN client template for WireGuard VPN Server
######################################################

1. Visit ``/admin/config/template/add/`` to add a new template.
2. Set ``Wireguard Client`` as **Name** (you can set whatever you want) and
   select ``VPN-client`` as **type** from the dropdown list.
3. The **Backend** field refers to the backend of the device this template can
   be applied to. For this example, we will leave it to ``OpenWRT``.
4. Select the correct VPN server from the dropdown for the **VPN** field. Here
   it is ``Wireguard``.
5. Ensure that **Automatic tunnel provisioning** is checked. This will make
   OpenWISP to automatically generate public and private keys and provision IP
   address for each WireGuard VPN client.
6. After clicking on **Save and continue editing** button, you will see details
   of *Wireguard* VPN server in **System Defined Variables**. The template
   configuration will be automatically generated which you can tweak
   accordingly. We will use the automatically generated VPN client configuration
   for this example.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-tutorial/template.png
    :alt: WireGuard VPN client template example

4. Apply Wireguard VPN template to devices
##########################################

**Note**: This step assumes that you already have a device registered on
OpenWISP. Register or create a device before proceeding.

1. Open the **Configuration** tab of the concerned device.
2. Select the *WireGuard Client* template.
3. Upon clicking on **Save and continue editing** button, you will see some
   entries in **System Defined Variables**. It will contain internal IP address,
   private and public key for the WireGuard client on the device along with
   details of WireGuard VPN server.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-tutorial/device-configuration.png
   :alt: WireGuard VPN device configuration example

**Voila!** You have successfully configured OpenWISP to manage WireGuard
tunnels for your devices.

How to setup VXLAN over WireGuard tunnels
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By following these steps, you will be able to setup layer 2 VXLAN tunnels
encapsulated in WireGuard tunnels which work on layer 3.

**Note:** This example uses **Shared systemwide (no organization)** option as
the organization for VPN server and VPN client template. You can use any
organization as long as VPN server, VPN client template and Device has same
organization.

1. Create VPN server configuration for VXLAN over WireGuard
###########################################################

1. Visit ``/admin/config/vpn/add/`` to add a new VPN server.
2. We will set **Name** of this VPN server ``Wireguard VXLAN`` and **Host** as
   ``wireguard-vxlan-server.mydomain.com`` (update this to point to your
   WireGuard VXLAN VPN server).
3. Select ``VXLAN over WireGuard`` from the dropdown as **VPN Backend**.
4. When using VXLAN over WireGuard, OpenWISP takes care of managing IP addresses
   (assigning an IP address to each VPN peer). You can create a new subnet or
   select an existing one from the dropdown menu. You can also assign an
   **Internal IP** to the WireGuard Server or leave it empty for OpenWISP to
   configure. This IP address will be used by the WireGuard interface on
   server.
5. We have set the **Webhook Endpoint** as ``https://wireguard-vxlan-server.mydomain.com:8081/trigger-update``
   for this example. You will need to update this according to you VPN upgrader
   endpoint. Set **Webhook AuthToken** to any strong passphrase, this will be
   used to ensure that configuration upgrades are requested from trusted
   sources.

   **Note**: If you are following this tutorial for also setting up WireGuard
   VPN server, just substitute ``wireguard-server.mydomain.com`` with hostname
   of your VPN server and follow the steps in next section.

6. Under the configuration section, set the name of WireGuard tunnel 1 interface.
   We have used ``wg0`` in this example.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-vxlan-tutorial/vpn-server-1.png
   :alt: WireGuard VPN VXLAN server configuration example 1

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-vxlan-tutorial/vpn-server-2.png
   :alt: WireGuard VPN VXLAN server configuration example 2

7. After clicking on **Save and continue editing**, you will see that OpenWISP
   has automatically created public and private key for WireGuard server in
   **System Defined Variables** along with internal IP address information.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-vxlan-tutorial/vpn-server-3.png
   :alt: WireGuard VXLAN VPN server configuration example 3

2. Deploy Wireguard VXLAN VPN Server
####################################

If you haven't already setup WireGuard on your VPN server, this will be a good
time do so. We recommend using the `ansible-wireguard-openwisp <https://github.com/openwisp/ansible-wireguard-openwisp>`_
role for installing WireGuard since it also installs scripts that allows
OpenWISP to manage WireGuard VPN server along with VXLAN tunnels.

Pay attention to the VPN server attributes used in your playbook. It should be same as
VPN server configuration in OpenWISP.

3. Create VPN client template for WireGuard VXLAN VPN Server
############################################################

1. Visit ``/admin/config/template/add/`` to add a new template.
2. Set ``Wireguard VXLAN Client`` as **Name** (you can set whatever you want) and
   select ``VPN-client`` as **type** from the dropdown list.
3. The **Backend** field refers to the backend of the device this template can
   be applied to. For this example, we will leave it to ``OpenWRT``.
4. Select the correct VPN server from the dropdown for the **VPN** field. Here
   it is ``Wireguard VXLAN``.
5. Ensure that **Automatic tunnel provisioning** is checked. This will make
   OpenWISP to automatically generate public and private keys and provision IP
   address for each WireGuard VPN client along with VXLAN Network Indentifier(VNI).
6. After clicking on **Save and continue editing** button, you will see details
   of *Wireguard VXLAN* VPN server in **System Defined Variables**. The template
   configuration will be automatically generated which you can tweak
   accordingly. We will use the automatically generated VPN client configuration
   for this example.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-vxlan-tutorial/template.png
    :alt: WireGuard VXLAN VPN client template example

4. Apply Wireguard VXLAN VPN template to devices
################################################

**Note**: This step assumes that you already have a device registered on
OpenWISP. Register or create a device before proceeding.

1. Open the **Configuration** tab of the concerned device.
2. Select the *WireGuard VXLAN Client* template.
3. Upon clicking on **Save and continue editing** button, you will see some
   entries in **System Defined Variables**. It will contain internal IP address,
   private and public key for the WireGuard client on the device and details of
   WireGuard VPN server along with VXLAN Network Identifier(VNI) of this device.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-vxlan-tutorial/device-configuration.png
   :alt: WireGuard VXLAN VPN device configuration example

**Voila!** You have successfully configured OpenWISP to manage VXLAN over
WireGuard tunnels for your devices.

How to configure automatic provisioning of subnets and IPs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following steps will help you configure automatic provisioning of subnets and IPs
for devices.

1. Create a Subnet and a Subnet Division Rule
#############################################

Create a master subnet under which automatically generated subnets will be provisioned.

**Note**: Choose the size of the subnet appropriately considering your use case.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/subnet.png
  :alt: Creating a master subnet example

On the same page, add a **subnet division rule** that will be used to provision subnets
under the master subnet.

The type of subnet division rule controls when subnets and IP addresses will be provisioned
for a device. The subnet division rule types currently implemented are described below.

Device Subnet Division Rule
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This rule type is triggered whenever a device configuration (``config.Config`` model)
is created for the organization specified in the rule.

Creating a new rule of "Device" type will also provision subnets and
IP addresses for existing devices of the organization automatically.

**Note**: a device without a configuration will not trigger this rule.

VPN Subnet Division Rule
^^^^^^^^^^^^^^^^^^^^^^^^

This rule is triggered when a VPN client template is assigned to a device,
provided the VPN server to which the VPN client template relates to has
the same subnet for which the subnet division rule is created.

**Note:** This rule will only work for **WireGuard** and **VXLAN over WireGuard**
VPN servers.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/subnet-division-rule.png
  :alt: Creating a subnet division rule example

In this example, **VPN subnet division rule** is used.

2. Create a VPN Server
######################

Now create a VPN Server and choose the previously created **master subnet** as the subnet for
this VPN Server.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/vpn-server.png
  :alt: Creating a VPN Server example

3. Create a VPN Client Template
###############################

Create a template, setting the **Type** field to **VPN Client** and **VPN** field to use the
previously created VPN Server.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/vpn-client.png
  :alt: Creating a VPN Client template example

**Note**: You can also check the **Enable by default** field if you want to automatically
apply this template to devices that will register in future.

4. Apply VPN Client Template to Devices
#######################################

With everything in place, you can now apply the VPN Client Template to devices.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/apply-template-to-device.png
  :alt: Adding template to device example

After saving the device, you should see all provisioned Subnets and IPs for this device
under `System Defined Variables <#system-defined-variables>`_.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/system-defined-variables.png
  :alt: Provisioned Subnets and IPs available as System Defined Variables example

Voila! You can now use these variables in configuration of the device. Refer to `How to use configuration variables <#how-to-use-configuration-variables>`_
section of this documentation to learn how to use configuration variables.

Important notes for using Subnet Division
#########################################

- In the above example Subnet, VPN Server, and VPN Client Template belonged to the **default** organization.
  You can use **Systemwide Shared** Subnet, VPN Server, or VPN Client Template too, but
  Subnet Division Rule will be always related to an organization. The Subnet Division Rule will only be
  triggered when such VPN Client Template will be applied to a Device having the same organization as Subnet Division Rule.

- You can also use the configuration variables for provisioned subnets and IPs in the Template.
  Each variable will be resolved differently for different devices. E.g. ``OW_subnet1_ip1`` will resolve to
  ``10.0.0.1`` for one device and ``10.0.0.55`` for another. Every device gets its own set of subnets and IPs.
  But don't forget to provide the default fall back values in the "default values" template field
  (used mainly for validation).

- The Subnet Division Rule will automatically create a reserved subnet, this subnet can be used
  to provision any IP addresses that have to be created manually. The rest of the master subnet
  address space **must not** be interfered with or the automation implemented in this module
  will not work.

- The above example used `VPN subnet division rule <#vpn-subnet-division-rule>`_. Similarly,
  `device subnet division rule <#device-subnet-division-rule>`_ can be used, which only requires
  `creating a subnet and a subnet division rule <#1-create-a-subnet-and-a-subnet-division-rule>`_.

Limitations of Subnet Division
##############################

In the current implementation, it is not possible to change "Size", "Number of Subnets" and
"Number of IPs" fields of an existing subnet division rule due to following reasons:

Size
^^^^

Allowing to change size of provisioned subnets of an existing subnet division rule
will require rebuilding of Subnets and IP addresses which has possibility of breaking
existing configurations.

Number of Subnets
^^^^^^^^^^^^^^^^^

Allowing to decrease number of subnets of an existing subnet division
rule can create patches of unused subnets dispersed everywhere in the master subnet.
Allowing to increase number of subnets will break the continuous allocation of subnets for
every device. It can also break configuration of devices.

Number of IPs
^^^^^^^^^^^^^

Allowing to decrease number of IPs of an existing subnet division rule
will lead to deletion of IP Addresses which can break configuration of devices being used.
It **is allowed** to increase number of IPs.

If you want to make changes to any of above fields, delete the existing rule and create a
new one. The automation will provision for all existing devices that meets the criteria
for provisioning. **WARNING**: It is possible that devices get different subnets and IPs
from previous provisioning.

Default Alerts / Notifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+-----------------------+---------------------------------------------------------------------+
| Notification Type     | Use                                                                 |
+-----------------------+---------------------------------------------------------------------+
| ``config_error``      | Fires when status of a device configuration changes to  ``error``.  |
+-----------------------+---------------------------------------------------------------------+
| ``device_registered`` | Fires when a new device is registered automatically on the network. |
+-----------------------+---------------------------------------------------------------------+

REST API Reference
------------------

Live documentation
~~~~~~~~~~~~~~~~~~

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/live-docu-api.png

A general live API documentation (following the OpenAPI specification) at ``/api/v1/docs/``.

Browsable web interface
~~~~~~~~~~~~~~~~~~~~~~~

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/browsable-api-ui.png

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
############

.. code-block:: text

    GET /api/v1/controller/device/

Create device
#############

.. code-block:: text

    POST /api/v1/controller/device/

Get device detail
#################

.. code-block:: text

    GET /api/v1/controller/device/{id}/

Download device configuration
#############################

.. code-block:: text

    GET /api/v1/controller/device/{id}/configuration/

The above endpoint triggers the download of a ``tar.gz`` file containing the generated configuration for that specific device.

Change details of device
########################

.. code-block:: text

    PUT /api/v1/controller/device/{id}/

Patch details of device
#######################

.. code-block:: text

    PATCH /api/v1/controller/device/{id}/

**Note**: To assign, unassign, and change the order of the assigned templates add,
remove, and change the order of the ``{id}`` of the templates under the ``config`` field in the JSON response respectively.
Moreover, you can also select and unselect templates in the HTML Form of the Browsable API.

The required template(s) from the organization(s) of the device will added automatically
to the ``config`` and cannot be removed.

**Example usage**: For assigning template(s) add the/their {id} to the config of a device,

.. code-block:: shell

    curl -X PATCH \
        http://127.0.0.1:8000/api/v1/controller/device/76b7d9cc-4ffd-4a43-b1b0-8f8befd1a7c0/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'content-type: application/json' \
        -d '{
                "config": {
                    "templates": ["4791fa4c-2cef-4f42-8bb4-c86018d71bd3"]
                }
            }'

**Example usage**: For removing assigned templates, simply remove the/their {id} from the config of a device,

.. code-block:: shell

    curl -X PATCH \
        http://127.0.0.1:8000/api/v1/controller/device/76b7d9cc-4ffd-4a43-b1b0-8f8befd1a7c0/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'content-type: application/json' \
        -d '{
                "config": {
                    "templates": []
                }
            }'

**Example usage**: For reordering the templates simply change their order from the config of a device,

.. code-block:: shell

    curl -X PATCH \
        http://127.0.0.1:8000/api/v1/controller/device/76b7d9cc-4ffd-4a43-b1b0-8f8befd1a7c0/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'cache-control: no-cache' \
        -H 'content-type: application/json' \
        -H 'postman-token: b3f6a1cc-ff13-5eba-e460-8f394e485801' \
        -d '{
                "config": {
                    "templates": [
                        "c5bbc697-170e-44bc-8eb7-b944b55ee88f",
                        "4791fa4c-2cef-4f42-8bb4-c86018d71bd3"
                    ]
                }
            }'

Delete device
#############

.. code-block:: text

    DELETE /api/v1/controller/device/{id}/

List device connections
#######################

.. code-block:: text

    GET /api/v1/controller/device/{id}/connection/

Create device connection
########################

.. code-block:: text

    POST /api/v1/controller/device/{id}/connection/

Get device connection detail
############################

.. code-block:: text

    GET /api/v1/controller/device/{id}/connection/{id}/

Change device connection detail
###############################

.. code-block:: text

    PUT /api/v1/controller/device/{id}/connection/{id}/

Patch device connection detail
##############################

.. code-block:: text

    PATCH /api/v1/controller/device/{id}/connection/{id}/

Delete device connection
########################

.. code-block:: text

    DELETE /api/v1/controller/device/{id}/connection/{id}/

List credentials
################

.. code-block:: text

    GET /api/v1/connection/credential/

Create credential
#################

.. code-block:: text

    POST /api/v1/connection/credential/

Get credential detail
#####################

.. code-block:: text

    GET /api/v1/connection/credential/{id}/

Change credential detail
########################

.. code-block:: text

    PUT /api/v1/connection/credential/{id}/

Patch credential detail
#######################

.. code-block:: text

    PATCH /api/v1/connection/credential/{id}/

Delete credential
#################

.. code-block:: text

    DELETE /api/v1/connection/credential/{id}/

List commands of a device
#########################

.. code-block:: text

    GET /api/v1/controller/device/{id}/command/

Execute a command a device
##########################

.. code-block:: text

    POST /api/v1/controller/device/{id}/command/

Get command details
###################

.. code-block:: text

    GET /api/v1/controller/device/{device_id}/command/{command_id}/

List device groups
##################

.. code-block:: text

    GET /api/v1/controller/group/

Create device group
###################

.. code-block:: text

    POST /api/v1/controller/group/

Get device group detail
#######################

.. code-block:: text

    GET /api/v1/controller/group/{id}/

Get device group from certificate common name
#############################################

.. code-block:: text

    GET /api/v1/controller/cert/{common_name}/group/

This endpoint can be used to retrieve group information and metadata by the
common name of a certificate used in a VPN client tunnel, this endpoint is
used in layer 2 tunneling solutions for firewall/captive portals.

It is also possible to filter device group by providing organization slug
of certificate's organization as show in the example below:

.. code-block:: text

    GET /api/v1/controller/cert/{common_name}/group/?org={org1_slug},{org2_slug}

Get device location
###################

.. code-block:: text


    GET /api/v1/controller/device/{id}/location/


Create device location
######################

.. code-block:: text

    PUT /api/v1/controller/device/{id}/location/

You can create ``DeviceLocation`` object by using primary
keys of existing ``Location`` and ``FloorPlan`` objects as shown in
the example below.

.. code-block:: json

    {
        "location": "f0cb5762-3711-4791-95b6-c2f6656249fa",
        "floorplan": "dfeb6724-aab4-4533-aeab-f7feb6648acd",
        "indoor": "-36,264"
    }

**Note:** The ``indoor`` field represents the coordinates of the
point placed on the image from the top left corner. E.g. if you
placed the pointer on the top left corner of the floorplan image,
its indoor coordinates will be ``0,0``.

.. code-block:: text

    curl -X PUT \
        http://127.0.0.1:8000/api/v1/controller/device/8a85cc23-bad5-4c7e-b9f4-ffe298defb5c/location/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'content-type: application/json' \
        -d '{
            "location": "f0cb5762-3711-4791-95b6-c2f6656249fa",
            "floorplan": "dfeb6724-aab4-4533-aeab-f7feb6648acd",
            "indoor": "-36,264"
            }'

You can also create related ``Location`` and ``FloorPlan`` objects for the
device directly from this endpoint.

The following example demonstrates creating related location
object in a single request.

.. code-block:: json

    {
        "location": {
            "name": "Via del Corso",
            "address": "Via del Corso, Roma, Italia",
            "geometry": {
                "type": "Point",
                "coordinates": [12.512124, 41.898903]
            },
            "type": "outdoor",
        }
    }

.. code-block:: text

    curl -X PUT \
        http://127.0.0.1:8000/api/v1/controller/device/8a85cc23-bad5-4c7e-b9f4-ffe298defb5c/location/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'content-type: application/json' \
        -d '{
                "location": {
                    "name": "Via del Corso",
                    "address": "Via del Corso, Roma, Italia",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [12.512124, 41.898903]
                    },
                    "type": "outdoor"
                }
            }'

**Note:** You can also specify the ``geometry`` in **Well-known text (WKT)**
format, like following:

.. code-block:: json

    {
        "location": {
            "name": "Via del Corso",
            "address": "Via del Corso, Roma, Italia",
            "geometry": "POINT (12.512124 41.898903)",
            "type": "outdoor",
        }
    }

Similarly, you can create ``Floorplan`` object with the same request.
But, note that a ``FloorPlan`` can be added to ``DeviceLocation`` only
if the related ``Location`` object defines an indoor location. The example
below demonstrates creating both ``Location`` and ``FloorPlan`` objects.

.. code-block:: text

    // This is not a valid JSON object. The JSON format is
    // only used for showing available fields.
    {
        "location.name": "Via del Corso",
        "location.address": "Via del Corso, Roma, Italia",
        "location.geometry.type": "Point",
        "location.geometry.coordinates": [12.512124, 41.898903]
        "location.type": "outdoor",
        "floorplan.floor": 1,
        "floorplan.image": floorplan.png,
    }

.. code-block:: text

    curl -X PUT \
        http://127.0.0.1:8000/api/v1/controller/device/8a85cc23-bad5-4c7e-b9f4-ffe298defb5c/location/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'content-type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW' \
        -F 'location.name=Via del Corso' \
        -F 'location.address=Via del Corso, Roma, Italia' \
        -F location.geometry.type=Point \
        -F 'location.geometry.coordinates=[12.512124, 41.898903]' \
        -F location.type=indoor \
        -F floorplan.floor=1 \
        -F 'floorplan.image=@floorplan.png'

**Note:** The request in above example uses ``multipart content-type``
for uploading floorplan image.

You can also use an existing ``Location`` object and create a new
floorplan for that location using this endpoint.

.. code-block:: text

    // This is not a valid JSON object. The JSON format is
    // only used for showing available fields.
    {
        "location": "f0cb5762-3711-4791-95b6-c2f6656249fa",
        "floorplan.floor": 1,
        "floorplan.image": floorplan.png
    }

.. code-block:: text

    curl -X PUT \
        http://127.0.0.1:8000/api/v1/controller/device/8a85cc23-bad5-4c7e-b9f4-ffe298defb5c/location/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'content-type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW' \
        -F location=f0cb5762-3711-4791-95b6-c2f6656249fa \
        -F floorplan.floor=1 \
        -F 'floorplan.image=@floorplan.png'

Change details of device location
#################################

.. code-block:: text

    PUT /api/v1/controller/device/{id}/location/

**Note:** This endpoint can be used to update related ``Location``
and ``Floorplan`` objects. Refer `examples of "Create device location"
section for information on payload format <#create-device-location>`_.

Delete device location
######################

.. code-block:: text

    DELETE /api/v1/controller/device/{id}/location/

Get device coordinates
######################

.. code-block:: text

    GET /api/v1/controller/device/{id}/coordinates/

**Note:** This endpoint is intended to be used by devices.

This endpoint skips multi-tenancy and permission checks if the
device ``key`` is passed as ``query_param`` because the system
assumes that the device is updating it's position.

.. code-block:: text

    curl -X GET \
        'http://127.0.0.1:8000/api/v1/controller/device/8a85cc23-bad5-4c7e-b9f4-ffe298defb5c/coordinates/?key=10a0cb5a553c71099c0e4ef236435496'

Update device coordinates
#########################

.. code-block:: text

    PUT /api/v1/controller/device/{id}/coordinates/

**Note:** This endpoint is intended to be used by devices.

This endpoint skips multi-tenancy and permission checks if the
device ``key`` is passed as ``query_param`` because the system
assumes that the device is updating it's position.

.. code-block:: json

    {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [12.512124, 41.898903]
        },
    }

.. code-block:: text

    curl -X PUT \
        'http://127.0.0.1:8000/api/v1/controller/device/8a85cc23-bad5-4c7e-b9f4-ffe298defb5c/coordinates/?key=10a0cb5a553c71099c0e4ef236435496' \
        -H 'content-type: application/json' \
        -d '{
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [12.512124, 41.898903]
                },
            }'

List locations
##############

.. code-block:: text

    GET /api/v1/controller/location/

You can filter using ``organization_slug`` to get list locations that
belongs to an organization.

.. code-block:: text

    GET /api/v1/controller/location/?organization_slug=<organization_slug>

Create location
###############

.. code-block:: text

    POST /api/v1/controller/location/

If you are creating an ``indoor`` location, you can use this endpoint
to create floorplan for the location.

The following example demonstrates creating floorplan along with location
in a single request.

.. code-block:: text

    {
        "name": "Via del Corso",
        "address": "Via del Corso, Roma, Italia",
        "geometry.type": "Point",
        "geometry.location": [12.512124, 41.898903],
        "type": "indoor",
        "is_mobile": "false",
        "floorplan.floor": "1",
        "floorplan.image": floorplan.png,
        "organization": "1f6c5666-1011-4f1d-bce9-fc6fcb4f3a05"
    }

.. code-block:: text

    curl -X POST \
        http://127.0.0.1:8000/api/v1/controller/location/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'content-type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW' \
        -F 'name=Via del Corso' \
        -F 'address=Via del Corso, Roma, Italia' \
        -F geometry.type=Point \
        -F 'geometry.coordinates=[12.512124, 41.898903]' \
        -F type=indoor \
        -F is_mobile=false \
        -F floorplan.floor=1 \
        -F 'floorplan.image=@floorplan.png' \
        -F organization=1f6c5666-1011-4f1d-bce9-fc6fcb4f3a05

**Note:** You can also specify the ``geometry`` in **Well-known text (WKT)**
format, like following:

.. code-block:: text

    {
        "name": "Via del Corso",
        "address": "Via del Corso, Roma, Italia",
        "geometry": "POINT (12.512124 41.898903)",
        "type": "indoor",
        "is_mobile": "false",
        "floorplan.floor": "1",
        "floorplan.image": floorplan.png,
        "organization": "1f6c5666-1011-4f1d-bce9-fc6fcb4f3a05"
    }

Get location details
####################

.. code-block:: text

    GET /api/v1/controller/location/{pk}/

Change location details
#######################

.. code-block:: text

    PUT /api/v1/controller/location/{pk}/

**Note**: Only the first floorplan data present can be
edited or changed. Setting the ``type`` of location to
outdoor will remove all the floorplans associated with it.

Refer `examples of "Create location"
section for information on payload format <#create-location>`_.

Delete location
###############

.. code-block:: text

    DELETE /api/v1/controller/location/{pk}/

List devices in a location
##########################

.. code-block:: text

    GET /api/v1/controller/location/{id}/device/

List locations with devices deployed (in GeoJSON format)
########################################################

**Note**: this endpoint will only list locations that have been assigned to a device.

.. code-block:: text

    GET /api/v1/controller/location/geojson/

You can filter using ``organization_slug`` to get list location of
devices from that organization.

.. code-block:: text

    GET /api/v1/controller/location/geojson/?organization_slug=<organization_slug>

List floorplans
###############

.. code-block:: text

    GET /api/v1/controller/floorplan/

You can filter using ``organization_slug`` to get list floorplans that
belongs to an organization.

.. code-block:: text

    GET /api/v1/controller/floorplan/?organization_slug=<organization_slug>

Create floorplan
################

.. code-block:: text

    POST /api/v1/controller/floorplan/

Get floorplan details
#####################

.. code-block:: text

    GET /api/v1/controller/floorplan/{pk}/

Change floorplan details
########################

.. code-block:: text

    PUT /api/v1/controller/floorplan/{pk}/

Delete floorplan
################

.. code-block:: text

    DELETE /api/v1/controller/floorplan/{pk}/

List templates
##############

.. code-block:: text

    GET /api/v1/controller/template/

Create template
###############

.. code-block:: text

    POST /api/v1/controller/template/

Get template detail
###################

.. code-block:: text

    GET /api/v1/controller/template/{id}/

Download template configuration
###############################

.. code-block:: text

    GET /api/v1/controller/template/{id}/configuration/

The above endpoint triggers the download of a ``tar.gz`` file
containing the generated configuration for that specific template.

Change details of template
##########################

.. code-block:: text

    PUT /api/v1/controller/template/{id}/

Patch details of template
#########################

.. code-block:: text

    PATCH /api/v1/controller/template/{id}/

Delete template
###############

.. code-block:: text

    DELETE /api/v1/controller/template/{id}/

List VPNs
#########

.. code-block:: text

    GET /api/v1/controller/vpn/

Create VPN
##########

.. code-block:: text

    POST /api/v1/controller/vpn/

Get VPN detail
##############

.. code-block:: text

    GET /api/v1/controller/vpn/{id}/

Download VPN configuration
##########################

.. code-block:: text

    GET /api/v1/controller/vpn/{id}/configuration/

The above endpoint triggers the download of a ``tar.gz`` file
containing the generated configuration for that specific VPN.

Change details of VPN
#####################

.. code-block:: text

    PUT /api/v1/controller/vpn/{id}/

Patch details of VPN
####################

.. code-block:: text

    PATCH /api/v1/controller/vpn/{id}/

Delete VPN
##########

.. code-block:: text

    DELETE /api/v1/controller/vpn/{id}/

List CA
#######

.. code-block:: text

    GET /api/v1/controller/ca/

Create new CA
#############

.. code-block:: text

    POST /api/v1/controller/ca/

Import existing CA
##################

.. code-block:: text

    POST /api/v1/controller/ca/

**Note**: To import an existing CA, only ``name``, ``certificate``
and ``private_key`` fields have to be filled in the ``HTML`` form or
included in the ``JSON`` format.

Get CA Detail
#############

.. code-block:: text

    GET /api/v1/controller/ca/{id}/

Change details of CA
####################

.. code-block:: text

    PUT /api/v1/controller/ca/{id}/

Patch details of CA
###################

.. code-block:: text

    PATCH /api/v1/controller/ca/{id}/

Download CA(crl)
################

.. code-block:: text

    GET /api/v1/controller/ca/{id}/crl/

The above endpoint triggers the download of ``{id}.crl`` file containing
up to date CRL of that specific CA.

Delete CA
#########

.. code-block:: text

    DELETE /api/v1/controller/ca/{id}/

Renew CA
########

.. code-block:: text

    POST /api/v1/controller/ca/{id}/renew/

List Cert
#########

.. code-block:: text

    GET /api/v1/controller/cert/

Create new Cert
###############

.. code-block:: text

    POST /api/v1/controller/cert/

Import existing Cert
####################

.. code-block:: text

    POST /api/v1/controller/cert/

**Note**: To import an existing Cert, only ``name``, ``ca``,
``certificate`` and ``private_key`` fields have to be filled
in the ``HTML`` form or included in the ``JSON`` format.

Get Cert Detail
###############

.. code-block:: text

    GET /api/v1/controller/cert/{id}/

Change details of Cert
######################

.. code-block:: text

    PUT /api/v1/controller/cert/{id}/

Patch details of Cert
#####################

.. code-block:: text

    PATCH /api/v1/controller/cert/{id}/

Delete Cert
###########

.. code-block:: text

    DELETE /api/v1/controller/cert/{id}/

Renew Cert
##########

.. code-block:: text

    POST /api/v1/controller/cert/{id}/renew/

Revoke Cert
###########

.. code-block:: text

    POST /api/v1/controller/cert/{id}/revoke/

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

+--------------+----------------------------------------------------------------------------------+
| **type**:    | ``tuple``                                                                        |
+--------------+----------------------------------------------------------------------------------+
| **default**: | .. code-block:: python                                                           |
|              |                                                                                  |
|              |   (                                                                              |
|              |     ('openwisp_controller.vpn_backends.OpenVpn', 'OpenVPN'),                     |
|              |     ('openwisp_controller.vpn_backends.Wireguard', 'WireGuard'),                 |
|              |     ('openwisp_controller.vpn_backends.VxlanWireguard', 'VXLAN over WireGuard'), |
|              |   )                                                                              |
+--------------+----------------------------------------------------------------------------------+

Available VPN backends for VPN Server objects. For more information, see `netjsonconfig VPN backends
<https://netjsonconfig.openwisp.org/en/latest/backends/vpn-backends.html>`_.

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
set to ``VPN`` and indicates whether configuration regarding the VPN tunnel is
provisioned automatically to each device using the template, eg:

- when using OpenVPN, new `x509 <https://tools.ietf.org/html/rfc5280>`_ certificates
  will be generated automatically using the same CA assigned to the related VPN object
- when using WireGuard, new pair of private and public keys
  (using `Curve25519 <http://cr.yp.to/ecdh.html>`_) will be generated, as well as
  an IP address of the subnet assigned to the related VPN object
- when using `VXLAN <https://tools.ietf.org/html/rfc7348>`_ tunnels over Wireguad,
  in addition to the configuration generated for WireGuard, a new VID will be generated
  automatically for each device if the configuration option "auto VNI" is turned on in
  the VPN object

All these auto generated configuration options will be available as
template variables.

The objects that are automatically created will also be removed when they are not
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

Defines the format of the ``common_name`` attribute of VPN client certificates
that are automatically created when using VPN templates which have ``auto_cert``
set to ``True``. A unique slug generated using `shortuuid <https://github.com/skorokithakis/shortuuid/>`_
is appended to the common name to introduce uniqueness. Therefore, resulting
common names will have ``{OPENWISP_CONTROLLER_COMMON_NAME_FORMAT}-{unique-slug}``
format.

**Note:** If the ``name`` and ``mac address`` of the device are equal,
the ``name`` of the device will be omitted from the common name to avoid redundancy.

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

``OPENWISP_CONTROLLER_HIDE_AUTOMATICALLY_GENERATED_SUBNETS_AND_IPS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-----------+
| **type**:    | ``bool``  |
+--------------+-----------+
| **default**: | ``False`` |
+--------------+-----------+

Setting this to ``True`` will hide subnets and IPs generated using `subnet division rules <#subnet-division-app>`_
from being displayed on the changelist view of Subnet and IP admin.

``OPENWISP_CONTROLLER_SUBNET_DIVISION_TYPES``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+---------------------------------------------------------------------------------------------------------+
| **type**:    | ``tuple``                                                                                               |
+--------------+---------------------------------------------------------------------------------------------------------+
| **default**: | .. code-block:: python                                                                                  |
|              |                                                                                                         |
|              |    (                                                                                                    |
|              |       ('openwisp_controller.subnet_division.rule_types.device.DeviceSubnetDivisionRuleType', 'Device'), |
|              |       ('openwisp_controller.subnet_division.rule_types.vpn.VpnSubnetDivisionRuleType', 'VPN'),          |
|              |    )                                                                                                    |
|              |                                                                                                         |
+--------------+---------------------------------------------------------------------------------------------------------+

`Available types for Subject Division Rule <#device-subnet-division-rule>`_ objects.
For more information on how to write your own types, read
`"Custom Subnet Division Rule Types" section of this documentation <#custom-subnet-division-rule-types>`_

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
`'How to define custom commands" <#how-to-define-new-options-in-the-commands-menu>`_ section.

``OPENWISP_CONTROLLER_DEVICE_GROUP_SCHEMA``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+------------------------------------------+
| **type**:    | ``dict``                                 |
+--------------+------------------------------------------+
| **default**: | ``{'type': 'object', 'properties': {}}`` |
+--------------+------------------------------------------+

Allows specifying JSONSchema used for validating meta-data of `Device Group <#device-groups>`_.

``OPENWISP_CONTROLLER_SHARED_MANAGEMENT_IP_ADDRESS_SPACE``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+----------+
| **type**:    | ``bool`` |
+--------------+----------+
| **default**: | ``True`` |
+--------------+----------+

By default, the system assumes that the address space of the management
tunnel is shared among all the organizations using the system, that is,
the system assumes there's only one management VPN, tunnel or other
networking technology to reach the devices it controls.

When set to ``True``, any device belonging to any
organization will never have the same ``management_ip`` as another device,
the latest device declaring the management IP will take the IP and any
other device who declared the same IP in the past will have the field
reset to empty state to avoid potential conflicts.

Set this to ``False`` if every organization has its dedicated management
tunnel with a dedicated address space that is reachable by the OpenWISP server.

``OPENWISP_CONTROLLER_DSA_OS_MAPPING``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+----------+
| **type**:    | ``dict`` |
+--------------+----------+
| **default**: | ``{}``   |
+--------------+----------+

OpenWISP Controller can figure out whether it should use the new OpenWrt syntax
for DSA interfaces (Distributed Switch Architecture) introduced in OpenWrt 21 by
reading the ``os`` field of the ``Device`` object. However, if the firmware you
are using has a custom firmware identifier, the system will not be able to figure
out whether it should use the new syntax and it will default to
`OPENWISP_CONTROLLER_DSA_DEFAULT_FALLBACK <#openwisp_controller_dsa_default_fallback>`_.

If you want to make sure the system can parse your custom firmware
identifier properly, you can follow the example below.

For the sake of the example, the OS identifier ``MyCustomFirmware 2.0``
corresponds to ``OpenWrt 19.07``, while ``MyCustomFirmware 2.1`` corresponds to
``OpenWrt 21.02``. Configuring this setting as indicated below will allow
OpenWISP to supply the right syntax automatically.

Example:

.. code-block:: python

    OPENWISP_CONTROLLER_DSA_OS_MAPPING = {
        'netjsonconfig.OpenWrt': {
            # OpenWrt >=21.02 configuration syntax will be used for
            # these OS identifiers.
            '>=21.02': [r'MyCustomFirmware 2.1(.*)'],
            # OpenWrt <=21.02 configuration syntax will be used for
            # these OS identifiers.
            '<21.02': [r'MyCustomFirmware 2.0(.*)']
        }
    }

**Note**: The OS identifier should be a regular expression as shown in above example.

``OPENWISP_CONTROLLER_DSA_DEFAULT_FALLBACK``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+----------+
| **type**:    | ``bool`` |
+--------------+----------+
| **default**: | ``True`` |
+--------------+----------+

The value of this setting decides whether to use DSA syntax
(OpenWrt >=21 configuration syntax) if openwisp-controller fails
to make that decision automatically.

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
``sample_config``, ``sample_pki``, ``sample_connection``, ``sample_geo``
& ``sample_subnet_division``. but you can name it how you want::

    django-admin startapp sample_config
    django-admin startapp sample_pki
    django-admin startapp sample_connection
    django-admin startapp sample_geo
    django-admin startapp sample_subnet_division

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
``mycontroller.sample_pki``, ``mycontroller.sample_connection``,
``mycontroller.sample_geo`` & ``mycontroller.sample_subnet_division`` to
``INSTALLED_APPS`` in your ``settings.py``, ensuring also that
``openwisp_controller.config``, ``openwisp_controller.geo``,
``openwisp_controller.pki``, ``openwisp_controller.connnection`` &
``openwisp_controller.subnet_division`` have been removed:

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
        # 'openwisp_controller.subnet_division', <-- comment out or delete this line
        'mycontroller.sample_config',
        'mycontroller.sample_pki',
        'mycontroller.sample_geo',
        'mycontroller.sample_connection',
        'mycontroller.sample_subnet_division',
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

Substitute ``mycontroller``, ``sample_config``, ``sample_pki``, ``sample_connection``,
``sample_geo`` & ``sample_subnet_division`` with the name you chose in step 1.

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
        'openwisp_controller.subnet_division',
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

6. Django Channels Setup
~~~~~~~~~~~~~~~~~~~~~~~~

Create ``asgi.py`` in your project folder and add following lines in it:

.. code-block:: python

    from channels.auth import AuthMiddlewareStack
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.security.websocket import AllowedHostsOriginValidator
    from django.core.asgi import get_asgi_application

    from openwisp_controller.routing import get_routes
    # You can also add your routes like this
    from my_app.routing import my_routes

    application = ProtocolTypeRouter(
        {   "http": get_asgi_application(),
            'websocket': AllowedHostsOriginValidator(
                AuthMiddlewareStack(URLRouter(get_routes() + my_routes))
            )
        }
    )

7. Other Settings
~~~~~~~~~~~~~~~~~

Add the following settings to ``settings.py``:

.. code-block:: python

    FORM_RENDERER = 'django.forms.renderers.TemplatesSetting'

    ASGI_APPLICATION = 'my_project.asgi.application'
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

- sample_subnet_division:
    - `sample_subnet_division/__init__.py <https://github.com/openwisp/openwisp-controller/tree/issues/400-subnet-subdivision-rule/tests/openwisp2/sample_subnet_division/__init__.py>`_.
    - `sample_subnet_division/apps.py <https://github.com/openwisp/openwisp-controller/tree/issues/400-subnet-subdivision-rule/tests/openwisp2/sample_subnet_division/apps.py>`_.

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
- `sample_subnet_division <https://github.com/openwisp/openwisp-controller/tree/issues/400-subnet-subdivision-rule/tests/openwisp2/sample_subnet_division/models.py>`_

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
    SUBNET_DIVISION_SUBNETDIVISIONRULE_MODEL = 'sample_subnet_division.SubnetDivisionRule'
    SUBNET_DIVISION_SUBNETDIVISIONINDEX_MODEL = 'sample_subnet_division.SubnetDivisionIndex'

Substitute ``sample_config``, ``sample_pki``, ``sample_connection``,
``sample_geo`` & ``sample_subnet_division`` with the name you chose in step 1.

9. Create database migrations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create database migrations::

    ./manage.py makemigrations

Now, to use the default ``administrator`` and ``operator`` user groups
like the used in the openwisp_controller module, you'll manually need to make a
migrations file which would look like:

- `sample_config/migrations/0002_default_groups_permissions.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/migrations/0002_default_groups_permissions.py>`_
- `sample_geo/migrations/0002_default_group_permissions.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/migrations/0002_default_group_permissions.py>`_
- `sample_pki/migrations/0002_default_group_permissions.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_pki/migrations/0002_default_group_permissions.py>`_
- `sample_connection/migrations/0002_default_group_permissions.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_connection/migrations/0002_default_group_permissions.py>`_
- `sample_subnet_division/migrations/0002_default_group_permissions.py <https://github.com/openwisp/openwisp-controller/tree/issues/400-subnet-subdivision-rule/tests/openwisp2/sample_subnet_division/migrations/0002_default_group_permissions.py>`_

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
- `sample_subnet_division admin.py <https://github.com/openwisp/openwisp-controller/tree/issues/400-subnet-subdivision-rule/tests/openwisp2/sample_subnet_division/admin.py>`_.

To introduce changes to the admin, you can do it in two main ways which are described below.

**Note**: for more information regarding how the django admin works, or how it can be customized,
please refer to `"The django admin site" section in the django documentation <https://docs.djangoproject.com/en/dev/ref/contrib/admin/>`_.

1. Monkey patching
##################

If the changes you need to add are relatively small, you can resort to monkey patching.

For example:

sample_config
^^^^^^^^^^^^^

.. code-block:: python

    from openwisp_controller.config.admin import (
        DeviceAdmin,
        DeviceGroupAdmin,
        TemplateAdmin,
        VpnAdmin,
    )

    # DeviceAdmin.fields += ['example'] <-- monkey patching example

sample_connection
^^^^^^^^^^^^^^^^^

.. code-block:: python

    from openwisp_controller.connection.admin import CredentialsAdmin

    # CredentialsAdmin.fields += ['example'] <-- monkey patching example

sample_geo
^^^^^^^^^^

.. code-block:: python

    from openwisp_controller.geo.admin import FloorPlanAdmin, LocationAdmin

    # FloorPlanAdmin.fields += ['example'] <-- monkey patching example

sample_pki
^^^^^^^^^^

.. code-block:: python

    from openwisp_controller.pki.admin import CaAdmin, CertAdmin

    # CaAdmin.fields += ['example'] <-- monkey patching example

sample_subnet_division
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from openwisp_controller.subnet_division.admin import SubnetDivisionRuleInlineAdmin

    # SubnetDivisionRuleInlineAdmin.fields += ['example'] <-- monkey patching example

2. Inheriting admin classes
###########################

If you need to introduce significant changes and/or you don't want to resort to
monkey patching, you can proceed as follows:

sample_config
^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^

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
^^^^^^^^^^

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

sample_subnet_division
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from openwisp_controller.subnet_division.admin import (
        SubnetAdmin as BaseSubnetAdmin,
        IpAddressAdmin as BaseIpAddressAdmin,
        SubnetDivisionRuleInlineAdmin as BaseSubnetDivisionRuleInlineAdmin,
    )
    from django.contrib import admin
    from swapper import load_model

    Subnet = load_model('openwisp_ipam', 'Subnet')
    IpAddress = load_model('openwisp_ipam', 'IpAddress')
    SubnetDivisionRule = load_model('subnet_division', 'SubnetDivisionRule')

    admin.site.unregister(Subnet)
    admin.site.unregister(IpAddress)
    admin.site.unregister(SubnetDivisionRule)

    @admin.register(Subnet)
    class SubnetAdmin(BaseSubnetAdmin):
        # add your changes here

    @admin.register(IpAddress)
    class IpAddressAdmin(BaseIpAddressAdmin):
        # add your changes here

    @admin.register(SubnetDivisionRule)
    class SubnetDivisionRuleInlineAdmin(BaseSubnetDivisionRuleInlineAdmin):
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
- `sample_subnet_division tests.py <https://github.com/openwisp/openwisp-controller/tree/issues/400-subnet-subdivision-rule/tests/openwisp2/sample_subnet_division/tests.py>`_

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
#####################################

Extending the `sample_config/views.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/views.py>`_
is required only when you want to make changes in the controller API,
Remember to change ``config_views`` location in ``urls.py`` in point 11 for extending views.

For more information about django views, please refer to the `views section in the django documentation <https://docs.djangoproject.com/en/dev/topics/http/views/>`_.

2. Extending the Geo API Views
##############################

Extending the `sample_geo/views.py <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/views.py>`_
is required only when you want to make changes in the geo API,
Remember to change ``geo_views`` location in ``urls.py`` in point 11 for extending views.

For more information about django views, please refer to the `views section in the django documentation <https://docs.djangoproject.com/en/dev/topics/http/views/>`_.

Custom Subnet Division Rule Types
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is possible to create your own `subnet division rule types <#subnet-division-app>`_.
The rule type determines when subnets and IPs will be provisioned and when they
will be destroyed.

You can create your custom rule types by extending
``openwisp_controller.subnet_division.rule_types.base.BaseSubnetDivisionRuleType``.

Below is an example to create a subnet division rule type that will provision
subnets and IPs when a new device is created and will delete them upon deletion
for that device.

.. code-block:: python

    # In mycontroller/sample_subnet_division/rules_types/custom.py

    from django.db.models.signals import post_delete, post_save
    from swapper import load_model

    from openwisp_controller.subnet_division.rule_types.base import (
        BaseSubnetDivisionRuleType,
    )

    Device = load_model('config', 'Device')

    class CustomRuleType(BaseSubnetDivisionRuleType):
        # The signal on which provisioning should be triggered
        provision_signal = post_save
        # The sender of the provision_signal
        provision_sender = Device
        # Dispatch UID for connecting provision_signal to provision_receiver
        provision_dispatch_uid = 'some_unique_identifier_string'

        # The signal on which deletion should be triggered
        destroyer_signal = post_delete
        # The sender of the destroyer_signal
        destroyer_sender = Device
        # Dispatch UID for connecting destroyer_signal to destroyer_receiver
        destroyer_dispatch_uid = 'another_unique_identifier_string'

        # Attribute path to organization_id
        # Example 1: If organization_id is direct attribute of provision_signal
        #            sender instance, then
        #   organization_id_path = 'organization_id'
        # Example 2: If organization_id is indirect attribute of provision signal
        #            sender instance, then
        #   organization_id_path = 'some_attribute.another_intermediate.organization_id'
        organization_id_path = 'organization_id'

        # Similar to organization_id_path but for the required subnet attribute
        subnet_path = 'subnet'

        # An intermediate method through which you can specify conditions for provisions
        @classmethod
        def should_create_subnets_ips(cls, instance, **kwargs):
            # Using "post_save" provision_signal, the rule should be only
            # triggered when a new object is created.
            return kwargs['created']

        # You can define logic to trigger provisioning for existing objects
        # using following classmethod. By default, BaseSubnetDivisionRuleType
        # performs no operation for existing objects.
        @classmethod
        def provision_for_existing_objects(cls, rule_obj):
            for device in Device.objects.filter(
                organization=rule_obj.organization
            ):
                cls.provision_receiver(device, created=True)

After creating a class for your custom rule type, you will need to set
`OPENWISP_CONTROLLER_SUBNET_DIVISION_TYPES <#openwisp-controller-subnet-division-types>`_
setting as follows:

.. code-block:: python

    OPENWISP_CONTROLLER_SUBNET_DIVISION_TYPES = (                                                                                           |
       ('openwisp_controller.subnet_division.rule_types.vpn.VpnSubnetDivisionRuleType', 'VPN'),
       ('openwisp_controller.subnet_division.rule_types.device.DeviceSubnetDivisionRuleType', 'Device'),
       ('mycontroller.sample_subnet_division.rules_types.custom.CustomRuleType', 'Custom Rule'),
    )

Registering new notification types
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can define your own notification types using
``register_notification_type`` function from OpenWISP Notifications.

For more information, see the relevant `documentation section about
registering notification types in openwisp-notifications
<https://github.com/openwisp/openwisp-notifications#registering--unregistering-notification-types>`_.

Once a new notification type is registered, you have to use the
`"notify" signal provided in openwisp-notifications
<https://github.com/openwisp/openwisp-notifications#sending-notifications>`_
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
