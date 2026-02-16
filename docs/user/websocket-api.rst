WebSocket API
=============

Real-time push updates for device commands and location data.

.. contents:: **Table of contents**:
    :depth: 2
    :local:

Overview
--------

The WebSocket API provides real-time, push-based communication for
monitoring device command execution and tracking mobile device locations.

Endpoints
---------

Device Command Updates
~~~~~~~~~~~~~~~~~~~~~~

Receive real-time updates when commands execute on devices.

.. code-block:: text

    ws://<host>:<port>/ws/controller/device/{device_id}/command

**Use Cases:**

- Monitor command execution status in real-time
- Track command output as it's collected from the device
- Build UI that updates instantly when commands complete

**Required Parameters:**

- ``device_id`` - UUID of the target device

**Permissions Required:**

- Superuser, OR
- Staff user with ``change_command`` permission on devices

Location Updates (Single Location)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Receive real-time updates for a specific mobile device's location.

.. code-block:: text

    ws://<host>:<port>/ws/loci/location/{location_id}/

**Use Cases:**

- Track a single vehicle on a map in real-time
- Monitor individual mobile device movement
- Display live location updates in dashboards

**Required Parameters:**

- ``location_id`` - UUID of the location to monitor

**Permissions Required:**

- Superuser, OR
- Staff user who is a manager of the device's organization

Location Broadcasting (Organization-wide)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Receive real-time location updates for all mobile devices in your
organizations.

.. code-block:: text

    ws://<host>:<port>/ws/loci/mobile-location/

**Use Cases:**

- Monitor fleet of vehicles across organization
- Display all mobile locations on organization map
- Track multiple devices simultaneously

**Required Parameters:**

- None (user-specific: receives updates for organizations they manage)

**Permissions Required:**

- Superuser (receives all organization locations), OR
- Staff user (receives locations only for organizations they manage)

Message Format Reference
------------------------

**Device Command Update**

Sample message payload:

.. code-block:: json

    {
        "type": "send.update",
        "model": "Command",
        "data": {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "device": "660f9511-f39c-42e5-b827-556766551111",
            "type": "Custom Command",
            "input": {"command": "uci show network"},
            "output": "network=lan\nnetwork.lan.type=bridge",
            "status": "in-progress",
            "connection": "770g0612-g49d-53f6-c938-667877662222",
            "created": "2024-02-15T10:30:00.000000Z",
            "modified": "2024-02-15T10:30:15.000000Z"
        }
    }

Message fields:

- ``id`` - Unique command identifier
- ``device`` - Device UUID that executed the command
- ``type`` - Command type (e.g., "Custom Command", "Reboot")
- ``input`` - Command parameters/input
- ``output`` - Command execution result
- ``status`` - Current status: ``in-progress``, ``success``, or ``failed``
- ``connection`` - Connection used to execute the command
- ``created`` - Timestamp when command was created
- ``modified`` - Timestamp of last update

**Location Update**

Sample message payload:

.. code-block:: json

    {
        "type": "send_message",
        "message": {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Mobile Unit A",
            "address": "123 Main Street, City, Country",
            "type": "device",
            "is_mobile": true,
            "geometry": {
                "type": "Point",
                "coordinates": [12.512124, 41.898903]
            }
        }
    }

Message fields:

- ``id`` - Unique location identifier
- ``name`` - Location name
- ``address`` - Physical address
- ``type`` - Location type (e.g., "device")
- ``is_mobile`` - Whether this is a mobile location
- ``geometry`` - GeoJSON geometry (Point with longitude, latitude
  coordinates)
