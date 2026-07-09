Configuration Variables
=======================

Sometimes the configuration is not exactly equal on all the devices, some
parameters are unique to each device or need to be changed by the user.

In these cases it is possible to use configuration variables in
conjunction with templates, this feature is also known as *configuration
context*, think of it like a dictionary which is passed to the function
which renders the configuration, so that it can fill variables according
to the passed context.

Different Types of Variables
----------------------------

The different ways in which variables are defined are described below in
the order (high to low) of their precedence.

.. contents::
    :depth: 2
    :local:

.. _user_defined_variables:

1. User Defined Device Variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the device configuration section you can find a section named
"Configuration variables" where it is possible to define the configuration
variables and their values, as shown in the example below:

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/device-context.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/device-context.png
    :alt: context

2. Predefined Device Variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each device gets the following attributes passed as configuration
variables:

- ``id``
- ``key``
- ``name``
- ``mac_address``

3. Group Variables
~~~~~~~~~~~~~~~~~~

Variables can also be defined in :doc:`./device-groups`.

Refer to :ref:`device_group_variables` for more information.

4. Organization Variables
~~~~~~~~~~~~~~~~~~~~~~~~~

Variables can also be defined at the organization level.

You can set the *organization variables* from the organization change page
``/admin/openwisp_users/organization/<organization-id>/change/``, under
the **Configuration Management Settings**.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/organization-variables.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/organization-variables.png
    :alt: organization variables

5. Global Variables
~~~~~~~~~~~~~~~~~~~

Variables can also be defined globally using the :ref:`context_setting`
setting, see also :doc:`How to Edit Django Settings
<../../../../user/django-settings>`.

6. Template Default Values
~~~~~~~~~~~~~~~~~~~~~~~~~~

It's possible to specify the default values of variables defined in a
template.

This allows to achieve 2 goals:

1. pass schema validation without errors (otherwise it would not be
   possible to save the template in the first place)
2. provide good default values that are valid in most cases but can be
   overridden in the device if needed

These default values will be overridden by the :ref:`User defined device
variables <user_defined_variables>`.

The default values of variables can be manipulated from the section
"configuration variables" in the edit template page:

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/template-default-values.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/template-default-values.png
    :alt: default values

.. _system_defined_variables:

7. System Defined Variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Predefined device variables, global variables and other variables that are
automatically managed by the system (e.g.: when using templates of type
VPN-client) are displayed in the admin UI as *System Defined Variables* in
read-only mode.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/system-defined-variables.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/system-defined-variables.png
    :alt: system defined variables

Example Usage of Variables
--------------------------

Here's a typical use case, the WiFi SSID and WiFi password. You don't want
to define this for every device, but you may want to allow operators to
easily change the SSID or WiFi password for a specific device without
having to re-define the whole wifi interface to avoid duplicating
information.

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

The default values can then be overridden at :ref:`device level
<user_defined_variables>` if needed, e.g.:

.. code-block:: json

    {
        "wlan0_ssid": "Room 23 ACME Hotel",
        "wlan0_password": "room_23pwd!321654"
    }

Implementation Details of Variables
-----------------------------------

Variables are implemented under the hood by the OpenWISP configuration
engine: netjsonconfig.

For more advanced technical information about variables, consult the
netjsonconfig documentation: `Basic Concepts, Context (configuration
variables)
<https://netjsonconfig.openwisp.org/en/latest/general/basics.html#template>`_.
