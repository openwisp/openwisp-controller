Sending Commands to Devices
===========================

.. contents:: **Table of Contents**:
    :depth: 3
    :local:

Single Device Commands
----------------------

Commands can be sent to one device at a time from the device detail page,
as shown in the GIF below:

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/single_command_demo.gif
    :target: https://github.com/openwisp/openwisp-controller/tree/docs/docs/single_command_demo.gif
    :alt: Sending a single command

Click the **Send Command** button, select the command type and fill in the
required inputs. The command is sent to the device and its status is shown
in the **Recent Commands** section of the device detail page.

To send the same command to many devices at once, refer to
:ref:`mass_commands`.

Default Commands
----------------

By default, there are three options in the **Send Command** dropdown:

1. Reboot
2. Change Password
3. Custom Command

While the first two options are self-explanatory, the **custom command**
option allows you to execute any command on the device as shown in the
example below.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/commands_demo.gif
    :target: https://github.com/openwisp/openwisp-controller/tree/docs/docs/commands_demo.gif
    :alt: Executing commands on device example

.. important::

    In order for this feature to work, a device needs to have at least one
    valid **Access Credential** (see :doc:`How to configure push updates
    <push-operations>`).

The **Send Command** button will be hidden until the device has at least
one **Access Credential**.

If you need to allow your users to quickly send specific commands that are
used often in your network regardless of your users' knowledge of Linux
shell commands, you can add new commands by following instructions in the
:ref:`defining_new_menu_options` section below.

.. note::

    You can also use the :ref:`REST API <controller_execute_command_api>`
    to execute commands on a device.

.. _mass_commands:

Mass Commands
-------------

Mass commands run the same command on many devices at once, for example to
reboot all the devices of a organization, as shown in the GIF below:

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/mass-command-tutorial/mass_command_demo.gif
    :target: https://github.com/openwisp/openwisp-controller/tree/docs/docs/mass-command-tutorial/mass_command_demo.gif
    :alt: Sending a mass command

Sending a Mass Command
~~~~~~~~~~~~~~~~~~~~~~

1. Open *Network Operations* > *Run Mass command*.
2. Choose the command, a **label** to recognize it later, and the
   **targets**: organization, device group and location. Combining targets
   narrows the selection.
3. Review the matched devices, uncheck any you want to leave out, and
   click **Execute**.

Superusers can leave every target empty to run the command on all the
devices, as shown in the GIF below:

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/mass-command-tutorial/mass_command_superuser.gif
    :target: https://github.com/openwisp/openwisp-controller/tree/docs/docs/mass-command-tutorial/mass_command_superuser.gif
    :alt: Running a mass command on all devices as a superuser

Other users must choose at least one target and can only use the commands
enabled for their organization (see
:ref:`openwisp_controller_organization_enabled_commands`).

From the Device List
~~~~~~~~~~~~~~~~~~~~

A mass command can also be started from the device list, as shown in the
GIF below:

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/mass-command-tutorial/mass_command_action.gif
    :target: https://github.com/openwisp/openwisp-controller/tree/docs/docs/mass-command-tutorial/mass_command_action.gif
    :alt: Sending a mass command to selected devices

Select the devices, choose *Execute mass command* from the actions
dropdown and click **Go**. Then choose the command and review the devices
as described above. The selected devices must belong to the same
organization.

Following the Results
~~~~~~~~~~~~~~~~~~~~~

After executing, the mass command page shows the status and output of each
device, updated in real time, as shown in the GIF below:

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/mass-command-tutorial/mass_command_results.gif
    :target: https://github.com/openwisp/openwisp-controller/tree/docs/docs/mass-command-tutorial/mass_command_results.gif
    :alt: Following the results of a mass command

- Devices which cannot run the command, for example because they have no
  access credentials, are marked as *skipped* together with the reason.
- Past mass commands are listed in *Network Operations* > *Mass commands*.
- Commands sent by a mass command also appear in the **Recent Commands**
  of each device, with a link back to the mass command.

REST API
~~~~~~~~

Mass commands can also be sent and followed through the :ref:`Batch
Command API <controller_batch_command_api>`.

.. _defining_new_menu_options:

Defining New Options in the Commands Menu
-----------------------------------------

.. note::

    If you're developing an OpenWISP extension, use the functions
    described in :ref:`registering_unregistering_commands` in the
    developer documentation instead of the setting described below.

Let's explore to define new custom commands to help users perform
additional management actions without having to be Linux/Unix experts.

We can do so by using the :ref:`OPENWISP_CONTROLLER_USER_COMMANDS
<openwisp_controller_user_commands>` Django setting.

The following example defines a simple command that can ``ping`` an input
``destination_address`` through a network interface, ``interface_name``.

.. code-block:: python

    # In yourproject/settings.py


    def ping_command_callable(destination_address, interface_name=None):
        command = f"ping -c 4 {destination_address}"
        if interface_name:
            command += f" -I {interface_name}"
        return command


    OPENWISP_CONTROLLER_USER_COMMANDS = [
        (
            "ping",
            {
                "label": "Ping",
                "schema": {
                    "title": "Ping",
                    "type": "object",
                    "required": ["destination_address"],
                    "properties": {
                        "destination_address": {
                            "type": "string",
                            "title": "Destination Address",
                        },
                        "interface_name": {
                            "type": "string",
                            "title": "Interface Name",
                        },
                    },
                    "message": "Destination Address cannot be empty",
                    "additionalProperties": False,
                },
                "callable": ping_command_callable,
            },
        )
    ]

The above code will add the *Ping* command in the user interface as show
in the GIF below:

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/ping_command_example.gif
    :target: https://github.com/openwisp/openwisp-controller/tree/docs/docs/ping_command_example.gif
    :alt: Adding a *ping* command

The :ref:`OPENWISP_CONTROLLER_USER_COMMANDS
<openwisp_controller_user_commands>` setting takes a ``list`` of ``tuple``
each containing two elements. The first element of the tuple should
contain an identifier for the command and the second element should
contain a ``dict`` defining configuration of the command.

.. _comand_configuration:

Command Configuration
~~~~~~~~~~~~~~~~~~~~~

The ``dict`` defining configuration for command should contain following
keys:

1. ``label``
++++++++++++

A ``str`` defining label for the command used internally by Django.

2. ``schema``
+++++++++++++

A ``dict`` defining `JSONSchema <https://json-schema.org/>`_ for inputs of
command. You can specify the inputs for your command, add rules for
performing validation and make inputs required or optional.

Here is a detailed explanation of the schema used in above example:

.. code-block:: python

    {
        # Name of the command displayed in *Send Command* widget
        "title": "Ping",
        # Use type *object* if the command needs to accept inputs
        # Use type *null* if the command does not accepts any input
        "type": "object",
        # Specify list of inputs that are required
        "required": ["destination_address"],
        # Define the inputs for the commands along with their properties
        "properties": {
            "destination_address": {
                # type of the input value
                "type": "string",
                # label used for displaying this input field
                "title": "Destination Address",
            },
            "interface_name": {
                "type": "string",
                "title": "Interface Name",
            },
        },
        # Error message to be shown if validation fails
        "message": "Destination Address cannot be empty",
        # Whether specifying addtionaly inputs is allowed from the input form
        "additionalProperties": False,
    }

This example uses only handful of properties available in JSONSchema. You
can experiment with other properties of JSONSchema for schema of your
command.

3. ``callable``
+++++++++++++++

A ``callable`` or ``str`` defining dotted path to a callable. It should
return the command (``str``) to be executed on the device. Inputs of the
command are passed as arguments to this callable.

The example above includes a callable(``ping_command_callable``) for
``ping`` command.

How to register or unregister commands
--------------------------------------

Refer to :ref:`registering_unregistering_commands` in the developer
documentation.
