WHOIS Lookup
============

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.3/whois/admin-details.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.3/whois/admin-details.png
    :alt: WHOIS admin details

.. important::

    The **WHOIS Lookup** feature is **disabled by default**.

    To enable it, follow the :ref:`controller_setup_whois_lookup` below.

.. contents:: **Table of contents**:
    :depth: 1
    :local:

Overview
--------

This feature displays information about the public IP address used by
devices to communicate with OpenWISP (via the ``last_ip`` field). It helps
identify the geographic location and ISP associated with the IP address,
which can be useful for troubleshooting network issues.

.. note::

    Once WHOIS Lookups are enabled, no manual intervention is needed:
    everything is handled automatically, including the refresh of old
    data. See :ref:`controller_whois_auto_management` for more
    information.

The retrieved information pertains to the Autonomous System (ASN)
associated with the device's public IP address and includes:

- ASN (Autonomous System Number)
- Organization name that owns the ASN
- CIDR block assigned to the ASN
- Physical address registered to the ASN
- Timezone of the ASN's registered location
- Coordinates (Latitude and Longitude)

.. note::

    This data also serves as a base for the :doc:`Estimated Location
    feature <./estimated-location>`.

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

6. Restart the application/containers if using ansible-openwisp2 or
   docker.
7. Run the ``clear_last_ip`` management command to clear the last IP
   address of any active device which doesn't have WHOIS info yet across
   all organizations (which will trigger the WHOIS lookup at the next
   config checksum check).

   - If using ansible-openwisp2 (default directory is /opt/openwisp2,
     unless changed in Ansible playbook configuration):

     .. code-block:: bash

         source /opt/openwisp2/env/bin/activate
         python /opt/openwisp2/manage.py clear_last_ip

   - If using docker:

     .. code-block:: bash

         docker exec -it <openwisp_container_name> sh
         python manage.py clear_last_ip

Viewing WHOIS Lookup Data
-------------------------

Once the WHOIS Lookup feature is enabled and WHOIS data is available, the
retrieved details can be viewed as follows:

- **Device Admin**: on the device's admin page, the WHOIS data is
  displayed alongside the device's last IP address.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.3/whois/admin-details.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.3/whois/admin-details.png
    :alt: WHOIS admin details

- **Device REST API**: Refer to :ref:`Device List <device_list_whois>` and
  :ref:`Device Detail <device_detail_whois>`.

.. _controller_whois_auto_management:

Triggers and Record Management
------------------------------

A WHOIS lookup is triggered automatically when:

- A new device registers and the last IP is a public IP address.
- A device's last IP address changes and is a public IP address.
- A device fetches its checksum **and** either no WHOIS record exists for
  the IP or the existing record is older than the :ref:`configured
  threshold <openwisp_controller_whois_refresh_threshold_days>`.

The lookup will only run if the device's last IP address is **public** and
WHOIS lookup is **enabled** for the device's organization.

When a device updates its last IP address, a WHOIS lookup is triggered for
the **new IP** and the **WHOIS record for the old IP** is deleted, unless
any active devices are associated with that IP address.

.. note::

    When a device with an associated WHOIS record is deleted, its WHOIS
    record is automatically removed, but only if no other active devices
    are associated with the same IP address.
