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

- Use JSON messages.
- Push real-time updates after the connection is established.
- Do not accept client messages: any data sent from the client is ignored.

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
- The user is marked as staff AND has ``add``, ``change`` and ``delete``
  permissions on the device model.

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
  - Has ``view`` or ``change`` permission on the location model,
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
- The user is marked as staff AND has ``view`` or ``change`` permission on
  the location model. In this case, updates are received only for the
  organizations the user manages.

Real-time Updates
+++++++++++++++++

After the connection is established, the server pushes a message every
time the geometry of any mobile location in a subscribed organization is
updated. The payload is identical to the one documented for the `2. Single
Location Updates`_ endpoint.
