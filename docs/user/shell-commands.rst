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

    You can also use the :ref:`REST API <controller_execute_command_api>`
    to execute commands on a device.

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

.. _mass_commands:

Mass Commands
-------------

Mass commands allow you to execute a command on multiple devices
simultaneously, rather than issuing commands one device at a time. This is
useful for rebooting all devices in a group, changing passwords across
multiple devices, or running diagnostics on all devices in an
organization.

Sending a Mass Command
~~~~~~~~~~~~~~~~~~~~~~

Open *Network Operations* > *Mass command execute* from the menu. The
first step asks for:

- the **command type** and its inputs, which change with the type
  selected;
- a **label** to identify the mass command later, and optional **notes**;
- the **targets**: organization, device group and location.

The targets decide which devices are matched. Using more than one narrows
the selection: a group and a location together match only the devices
which are in that group *and* at that location.

Superusers can leave every target empty to run the command on all the
devices of the system. Other users must choose at least one target, and
only see the command types enabled for their organizations (see
:ref:`openwisp_controller_organization_enabled_commands`).

Sending a Mass Command to Selected Devices
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A mass command can also be started from the device list: select the
devices with their checkboxes, choose *Execute mass command* from the
actions dropdown and click *Go*.

The first step opens with the selection already applied: a message at the
top of the page states how many devices the command will run on, and the
organization is filled in and cannot be changed, while device group and
location are not asked for, since the devices are already known.

The selected devices must belong to the same organization, otherwise the
action refuses to start. The exception is a superuser selecting every
device of the system: the command then runs on all of them and no target
is asked for.

The rest of the workflow is the same as described below: the devices can
still be reviewed and left out before executing.

Reviewing the Devices
~~~~~~~~~~~~~~~~~~~~~

The second step shows a summary of the command and the list of the devices
it matched.

Devices can be left out by unchecking them: the counter and the *Execute
on N devices* button follow the selection, which is kept while paging
through the list. *Back* returns to the first step with the form still
filled in.

The mass command starts when the *Execute* button is clicked.

Following the Results
~~~~~~~~~~~~~~~~~~~~~

After executing, the mass command page opens. It shows the status of the
mass command, how many devices are affected, the devices which were
skipped, and one row per device with its status and output.

The rows are updated in real time, so the page does not need to be
reloaded to follow the progress. The table can be searched by device name
and filtered by status, device group and location (and by organization for
superusers).

.. note::

    Commands are executed asynchronously in the background: each device is
    handled by an independent background task, so how many devices are
    contacted at the same time depends on the concurrency of the Celery
    workers. A mass command sent to many devices keeps updating for a
    while after the page is opened.

Finding Past Mass Commands
~~~~~~~~~~~~~~~~~~~~~~~~~~

*Network Operations* > *Mass command admin* lists the mass commands which
were sent, most recent first.

The list can be searched by label, notes, organization, device, location
and group name, and filtered by organization, status, type, group and
location. Clicking a mass command opens the page described above.

Skipped Devices
~~~~~~~~~~~~~~~

A device is skipped when the command cannot be created for it, for example
when the device has no access credentials, or when the command type is not
enabled for its organization.

Skipped devices are not executed, but they are shown: the **Skipped
devices** field summarizes how many there are and why, and each one is
listed in the results table with the *skipped* status and the reason as
its output. They can be found with the status filter.

Using the API
~~~~~~~~~~~~~

The same operations are available over the REST API, which also accepts an
explicit list of devices instead of the targets described above. Refer to
the :ref:`Batch Command API <controller_batch_command_api>` documentation
for the available endpoints, request parameters and examples.
