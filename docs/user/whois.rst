WHOIS Lookup
============

.. important::

    The **WHOIS Lookup** feature is disabled by default.

    To enable this feature, follow the `setup instructions
    <controller_setup_whois_lookup_>`_ below, then activate it via the
    :ref:`global setting or from the admin interface
    <OPENWISP_CONTROLLER_WHOIS_ENABLED>`.

.. warning::

    If :ref:`OPENWISP_CONTROLLER_WHOIS_ENABLED` is set to ``True`` but the
    required environment variables are not defined, an
    ``ImproperlyConfigured`` exception will be raised.

    Both :ref:`OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT` and
    :ref:`OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY` must be set to allow
    per-organization control of the WHOIS Lookup feature. If either is
    missing, the feature will be globally disabled and unavailable in the
    admin interface.

The WHOIS Lookup feature retrieves information about the last public IP
address reported by a device to assist with device identification and
management.

The fetched details include:

- ASN (Autonomous System Number)
- CIDR block
- Physical address
- Timezone
- Name of the organization associated with the ASN

WHOIS lookup is triggered when a new device is registered or when a device
fetches its checksum. However, for a WHOIS lookup to actually occur, the
following conditions must be met:

- The device’s last IP is public.
- No WHOIS record exists for that IP.
- WHOIS is enabled for the device's organization.

If multiple devices share the same IP and one of them switches to a new
IP, a lookup is triggered for the new IP and the old record is deleted.
Devices still on the old IP can re-trigger the lookup if needed.

.. _controller_setup_whois_lookup:

Steps to obtain account ID and license key
------------------------------------------

1. Create a MaxMind account: `Create Account
   <https://www.maxmind.com/en/geolite2/signup>`_

   If you already have an account, simply **Sign In**.

2. Navigate to **Manage License Keys** .. image::
   https://github.com/user-attachments/assets/0c2f693f-d2f5-4811-abd1-6148750380e9
3. Generate a new license key and name it as you prefer .. image::
   https://github.com/user-attachments/assets/57df27bc-4f9d-4701-88bf-91e6b715e4a6
4. Copy the **Account ID** and **License Key**, then set them as the
   environment variables :ref:`OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT`
   and :ref:`OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY` in your project.
