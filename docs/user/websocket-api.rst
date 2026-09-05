WebSocket API Reference
=======================

.. contents:: **Table of contents**:
    :depth: 2
    :local:

Overview
--------

The WebSocket API provides real-time, push-based updates for device
command execution and for mobile device location tracking.

All endpoints:

- Use JSON-encoded messages on the wire. The payload examples below are
  shown in JavaScript-style notation with inline comments for readability.
- Push real-time updates after the connection is established.
- Do not accept client messages: any data sent from the client is ignored.
  The only exception is the mass command endpoint, which accepts the
  single request documented below.

Authentication and Authorization
--------------------------------

All WebSocket endpoints require an authenticated user. Authentication
relies on the standard Django session: connect from a browser context
where the user is logged in to the OpenWISP admin so that the session
cookie is sent during the WebSocket handshake.

A connection is accepted only if the user is authorized to access the
requested resource. The connection is closed immediately if authentication
or authorization fails.

Per-endpoint authorization rules are documented below.

Connection Endpoints
--------------------

1. Device Command Updates
~~~~~~~~~~~~~~~~~~~~~~~~~

Connection URL:

::

    wss://<host>/ws/controller/device/<device_id>/command

Scope
+++++

Command execution events for a single device.

Authorization
+++++++++++++

A user is authorized if:

- The user is a superuser, OR
- The user is marked as staff AND has the ``config.add_device``,
  ``config.change_device`` and ``config.delete_device`` permissions.

Real-time Updates
+++++++++++++++++

After the connection is established, the server pushes one message every
time a command for the device is updated (for example when its status
changes from ``in-progress`` to ``success`` or ``failed``):

.. code-block:: javascript

    {
        "model": "Command",
        "data": {
            "id": "<uuid>",              // Command identifier
            "device": "<uuid>",          // Device identifier
            "connection": "<uuid>",      // Connection used to run the command (nullable)
            "type": "<string>",          // Command type display name (e.g. "Custom Command")
            "input": { /* ... */ },      // Command input (structure depends on type)
            "output": "<string>",        // Command output collected so far
            "status": "<string>",        // "in-progress", "success" or "failed"
            "created": "<datetime>",     // Creation timestamp (ISO 8601)
            "modified": "<datetime>"     // Last modification timestamp (ISO 8601)
        }
    }

2. Single Location Updates
~~~~~~~~~~~~~~~~~~~~~~~~~~

Connection URL:

::

    wss://<host>/ws/loci/location/<location_id>/

Scope
+++++

Coordinate changes for a single mobile location.

Authorization
+++++++++++++

A user is authorized if:

- The user is a superuser, OR
- The user:

  - Is marked as staff,
  - Has the ``geo.view_location`` or ``geo.change_location`` permission,
  - Is an organization manager for the location's organization.

Real-time Updates
+++++++++++++++++

After the connection is established, the server pushes a message every
time the location's geometry is updated:

.. code-block:: javascript

    {
        "id": "<uuid>",                  // Location identifier
        "name": "<string>",              // Location name
        "address": "<string>",           // Physical address
        "type": "<string>",              // Location type (e.g. "outdoor")
        "is_mobile": <boolean>,          // Whether the location is mobile
        "geometry": {                    // GeoJSON Point
            "type": "Point",
            "coordinates": [<longitude>, <latitude>]
        }
    }

3. Organization-wide Location Updates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Connection URL:

::

    wss://<host>/ws/loci/location/

Scope
+++++

Coordinate changes for every mobile location belonging to the
organizations managed by the authenticated user. Useful for displaying a
live map of an entire fleet.

Authorization
+++++++++++++

A user is authorized if:

- The user is a superuser (receives updates for every organization), OR
- The user is marked as staff AND has the ``geo.view_location`` or
  ``geo.change_location`` permission. In this case, updates are received
  only for the organizations the user manages.

Real-time Updates
+++++++++++++++++

After the connection is established, the server pushes a message every
time the geometry of any mobile location in a subscribed organization is
updated. The payload is identical to the one documented for the `2. Single
Location Updates`_ endpoint.

4. Mass Command Updates
~~~~~~~~~~~~~~~~~~~~~~~

Connection URL:

::

    wss://<host>/ws/controller/batch-command/<batch_command_id>

Scope
+++++

Progress of a single mass command: its status and the result of every
device it runs on. See :ref:`mass_commands`.

Authorization
+++++++++++++

A user is authorized if:

- The user is a superuser, OR
- The user is marked as staff AND has the ``connection.view_batchcommand``
  or ``connection.change_batchcommand`` permission AND manages the
  organization of the mass command.

Real-time Updates
+++++++++++++++++

The server pushes a message every time the mass command or one of its
commands changes. The ``type`` field tells the two apart.

When the mass command itself changes, for example when it moves from
``idle`` to ``in-progress``:

.. code-block:: javascript

    {
        "type": "batch_status",
        "id": "<uuid>",                  // Mass command identifier
        "label": "<string>",             // Label given when it was sent
        "notes": "<string>",             // Notes given when it was sent
        "input": { /* ... */ },          // Command input, masked for "change_password"
        "organization": "<uuid>",        // Organization, null when system wide
        "group": "<uuid>",               // Device group target, null when not used
        "location": "<uuid>",            // Location target, null when not used
        "status": "<string>",            // "idle", "in-progress", "success" or "failed"
        "created": "<string>",           // ISO 8601 timestamp
        "modified": "<string>",          // ISO 8601 timestamp
        "affected_devices": <integer>,   // Number of devices the command runs on
        "skipped_count": <integer>,      // Number of devices which were skipped
        "skipped_preview": [ /* ... */], // First and last skipped devices, with the reason
        "total_rows": <integer>          // Affected plus skipped devices
    }

The status and the timestamps are sent as they are stored, without
translation or formatting, so that each client can render them with its
own language and time zone.

When the command of one device changes:

.. code-block:: javascript

    {
        "type": "command_update",
        "id": "<uuid>",                  // Command identifier
        "device": "<uuid>",              // Device identifier
        "device_name": "<string>",       // Device name
        "connection": "<uuid>",          // Device connection used, may be null
        "batch_command": "<uuid>",       // Mass command this command belongs to
        "status": "<string>",            // "in-progress", "success" or "failed"
        "output": "<string>",            // Output collected so far
        "created": "<string>",           // ISO 8601 timestamp
        "modified": "<string>",          // ISO 8601 timestamp
        "index": <integer>,              // Position of the row, sent only for new commands
        "affected_devices": <integer>,   // Commands created so far, sent with "index"
        "total_rows": <integer>          // Affected plus skipped devices, sent with "index"
    }

Requesting the Current State
++++++++++++++++++++++++++++

A client which connects while the mass command is already running can ask
for the results it missed:

.. code-block:: javascript

    {
        "type": "request_current_state",
        "page": 1,                       // Page of results, 20 rows per page
        "filters": {                     // Optional, the filters the page is showing
            "q": "<string>",             // Search term matched against the device name
            "status": "<string>",        // Command status, or "skipped"
            "location_id": "<uuid>",     // Location of the device
            "group_id": "<uuid>",        // Device group
            "organization_id": "<uuid>"  // Organization of the device
        }
    }

Every filter is optional and an empty string means the filter is not
active. The filters are applied before the results are paginated, so a
client which is showing a filtered table receives the same rows it would
get by reloading the page.

The server replies with one message holding that page:

.. code-block:: javascript

    {
        "type": "batch_state",
        "batch_status": { /* ... */ },   // Batch serializer fields, including
                                         // the command type, but without
                                         // "skipped_devices" or "total_rows"
        "commands": [ /* ... */ ],       // Rows of the requested page. Command
                                         // rows include the command type and omit
                                         // event-only fields such as "index".
                                         // Their "output" is a 100-character tail.
        "page": <integer>,               // Effective page after bounds checking
        "total_rows": <integer>          // Rows matching the filters, for the paginator
    }

Rows of devices which were skipped are included in ``commands`` with
``is_skipped`` set to ``true``, a ``status`` of ``skipped`` and the reason
in ``output``.
