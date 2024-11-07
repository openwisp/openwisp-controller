Sending Commands to Devices
===========================

.. contents:: **Table of Contents**:
    :depth: 3
    :local:

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

    If you're an advanced user and want to learn how to register commands
    programmatically, refer to the
    :ref:`registering_unregistering_commands` section.

.. _defining_new_menu_options:

Defining New Options in the Commands Menu
-----------------------------------------

Let's explore to define new custom commands to help users perform
additional management actions without having to be Linux/Unix experts.

We can do so by using the ``OPENWISP_CONTROLLER_USER_COMMANDS`` django
setting.

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

The ``OPENWISP_CONTROLLER_USER_COMMANDS`` setting takes a ``list`` of
``tuple`` each containing two elements. The first element of the tuple
should contain an identifier for the command and the second element should
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
