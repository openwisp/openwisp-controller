Approximate Location
====================

.. important::

    The **Approximate Location** feature is **disabled by default**.

    Before enabling it, the :doc:`WHOIS Lookup feature <whois>` must be
    enabled. Then set
    :ref:`OPENWISP_CONTROLLER_APPROXIMATE_LOCATION_ENABLED` to ``True``

.. contents:: **Table of contents**:
    :depth: 1
    :local:

Overview
--------

The Approximate Location feature automatically creates or updates a
device’s location based on latitude and longitude information retrieved
from the WHOIS Lookup feature.

Trigger Conditions
------------------

Approximate Location is triggered when:

- A **fresh WHOIS lookup** is performed for a device.
- Or when a WHOIS record already exists for the device’s IP **and**:

  - The device’s last IP address is **public**.
  - WHOIS lookup and Approximate Location is **enabled** for the device’s
    organization.

Behavior
--------

The system will **attach the already existing matching location** of
another device with same ip to the current device if:

- Only one device is found with that IP and it has a location.
- The current device **has no location** or that location is
  **approximate**.

If there are multiple devices with location for the same IP, the system
will **not attach any location** to the current device and a notification
will be sent suggesting the user to manually assign/create a location for
the device.

If there is **no matching location**, a new approximate location is
created or the existing one is updated using coordinates from the WHOIS
record, but only if the existing location is approximate.
