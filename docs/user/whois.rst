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
- Coordinates (Latitude and Longitude)

Trigger Conditions
------------------

A WHOIS lookup is triggered automatically when:

- A new device is registered.
- A device fetches its checksum.

However, the lookup will only run if **all** the following conditions are
met:

- The device is either **newly created** or has a **changed last IP**.
- The device's last IP address is **public**.
- There is **no existing WHOIS record** for that IP.
- WHOIS lookup is **enabled** for the device's organization.

Managing WHOIS Records
----------------------

If a device updates its last IP address, lookup is triggered for the **new
IP** and the **WHOIS record for the old IP** is deleted if no active
devices are associated with that IP address.

.. note::

    When a device with an associated WHOIS record is deleted, its WHOIS
    record is automatically removed only if no active devices are
    associated with that IP address.

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
   address of **all active devices across organizations**.

   - If using ansible-openwisp2 (default directory is /opt/openwisp2,
     unless changed in Ansible playbook configuration):

     .. code-block:: bash

         source /opt/openwisp2/env/bin/activate
         python /opt/openwisp2/src/manage.py clear_last_ip

   - If using docker:

     .. code-block:: bash

         docker exec -it <openwisp_container_name> sh
         python manage.py clear_last_ip

Viewing WHOIS Lookup Data
-------------------------

Once the WHOIS Lookup feature is enabled and WHOIS data is available, the
retrieved details can be viewed in the following locations:

- **Device Admin**: On the device's admin page, the WHOIS data is
  displayed alongside the device's last IP address.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.3/whois-admin-details.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.3/whois-admin-details.png
    :alt: WHOIS admin details

- **Device REST API**: See WHOIS details in the :ref:`Device List
  <device_list_whois>` and :ref:`Device Detail <device_detail_whois>`
  responses.
