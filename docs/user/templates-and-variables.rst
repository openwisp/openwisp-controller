Template and Variables
----------------------

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

The different ways in which variables are defined are described below in
the order (high to low) of their precedence:

1. `User defined device variables <#user-defined-device-variables>`_
2. `Predefined device variables <#predefined-device-variables>`_
3. `Group variables <#group-variables>`_
4. `Organization variables <#organization-variables>`_
5. `Global variables <#global-variables>`_
6. `Template default values <#template-default-values>`_

User defined device variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the device configuration section you can find a section named
"Configuration variables" where it is possible to define the configuration
variables and their values, as shown in the example below:

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/device-context.png
   :alt: context

Predefined device variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each device gets the following attributes passed as configuration variables:

* ``id``
* ``key``
* ``name``
* ``mac_address``

Group variables
~~~~~~~~~~~~~~~

Variables can also be defined in `Device groups <#device-groups>`__.

Refer the `Group configuration variables <group-configuration-variables>`_
section for detailed information.

Organization variables
~~~~~~~~~~~~~~~~~~~~~~

Variables can also be defined at the organization level.

You can set the *organization variables* from the organization change page
``/admin/openwisp_users/organization/<organization-id>/change/``, under the
**Configuration Management Settings**.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/organization-variables.png
  :alt: organization variables

Global variables
~~~~~~~~~~~~~~~~

Variables can also be defined globally using the
`OPENWISP_CONTROLLER_CONTEXT <#openwisp-controller-context>`_ setting.

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

System defined variables
~~~~~~~~~~~~~~~~~~~~~~~~

Predefined device variables, global variables and other variables that
are automatically managed by the system (eg: when using templates of
type VPN-client) are displayed in the admin UI as *System Defined Variables*
in read-only mode.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/system-defined-variables.png
   :alt: system defined variables

**Note:** `Group configuration variables <#group-configuration-variables>`__
are also added to the **System Defined Variables** of the device.

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
