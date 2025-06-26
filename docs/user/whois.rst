WHOIS Lookup
============

.. important::

    The **WHOIS Lookup** feature is **disabled by default**.

    To enable it, follow the `setup steps
    <controller_setup_whois_lookup_>`_ below.

.. contents:: **Table of contents**:
    :depth: 1
    :local:

Overview
--------

The WHOIS Lookup feature displays information about the public IP address
used by devices to communicate with OpenWISP (via the ``last_ip`` field).
It helps identify the geographic location and ISP associated with the IP
address, which can be useful for troubleshooting network issues.

The retrieved information pertains to the Autonomous System (ASN)
associated with the device's public IP address and includes:

- ASN (Autonomous System Number)
- Organization name that owns the ASN
- CIDR block assigned to the ASN
- Physical address registered to the ASN
- Timezone of the ASN's registered location

Trigger Conditions
------------------

A WHOIS lookup is triggered automatically when:

- A new device is registered.
- A device fetches its checksum.

However, the lookup will only run if **all** the following conditions are
met:

- The device's last IP address is **public**.
- There is **no existing WHOIS record** for that IP.
- WHOIS lookup is **enabled** for the device's organization.

Behavior with Shared IP Addresses
---------------------------------

If multiple devices share the same public IP address and one of them
switches to a different IP, the following occurs:

- A lookup is triggered for the **new IP**.
- The WHOIS record for the **old IP** is deleted.
- The next time a device still using the old IP fetches its checksum, a
  new lookup is triggered, ensuring up-to-date data.

.. note::

    When a device with an associated WHOIS record is deleted, its WHOIS
    record is automatically removed.

.. _controller_setup_whois_lookup:

Setup Instructions
------------------

1. Create a MaxMind account: `Sign up here
   <https://www.maxmind.com/en/geolite2/signup>`_.

   If you already have an account, just **Sign In**.

2. Go to **Manage License Keys** in your MaxMind dashboard.
3. Generate a new license key and name it as you prefer.
4. Copy both the **Account ID** and **License Key**.
5. Set the following settings accordingly:

   - Set :ref:`OPENWISP_CONTROLLER_WHOIS_ENABLED` to ``True``.
   - Set :ref:`OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT` to **Account ID**.
   - Set :ref:`OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY` to **License Key**.
