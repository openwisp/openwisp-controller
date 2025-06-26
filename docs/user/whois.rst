WHOIS Lookup
============

.. important::

    The **WHOIS Lookup** feature is **disabled by default**.

    To enable it, follow the `setup steps
    <controller_setup_whois_lookup_>`_ below, then activate the feature
    via the :ref:`global setting or from the admin interface
    <OPENWISP_CONTROLLER_WHOIS_ENABLED>`.

.. warning::

    If :ref:`OPENWISP_CONTROLLER_WHOIS_ENABLED` is set to ``True``, but
    the required environment variables are not defined, an
    ``ImproperlyConfigured`` exception will be raised.

    You must set both :ref:`OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT` and
    :ref:`OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY` for the WHOIS Lookup
    feature to work. If either is missing, the feature will be globally
    disabled and hidden from the admin interface.

Overview
--------

The WHOIS Lookup feature fetches public IP address details reported by a
device. This helps identify and manage devices more effectively.

The retrieved information includes:

- ASN (Autonomous System Number)
- CIDR block
- Physical address
- Timezone
- Organization name linked to the ASN

Trigger Conditions
------------------

A WHOIS lookup is automatically triggered when:

- A new device is registered.
- A device fetches its checksum.

However, it will only run if **all** the following conditions are true:

- The device’s last IP address is **public**.
- There is **no existing WHOIS record** for that IP.
- WHOIS is **enabled** for the device's organization.

Behavior with Shared IPs
------------------------

If multiple devices share the same public IP, for which WHOIS record
exists, and one of them switches to a new IP:

- A lookup will be triggered for the **new IP**.
- The WHOIS record for the **old IP** will be deleted.
- Devices still using the old IP will trigger a new lookup the next time
  they fetch their checksum, ensuring up-to-date data.

**Note**: The WHOIS record is automatically deleted when the device
associated with that ip is deleted.

.. _controller_setup_whois_lookup:

Setup Instructions: Getting Account ID and License Key
------------------------------------------------------

1. Create a MaxMind account: `Sign up here
   <https://www.maxmind.com/en/geolite2/signup>`_

   If you already have an account, just **Sign In**.

2. Go to **Manage License Keys** in your MaxMind dashboard.
3. Generate a new license key and name it as you prefer.
4. Copy both the **Account ID** and **License Key**.
5. Set them as environment variables in your project:

   - :ref:`OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT`
   - :ref:`OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY`
