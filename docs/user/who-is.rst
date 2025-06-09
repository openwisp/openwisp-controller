WHOIS lookup
============

.. important::

    The WhoIs lookup feature is disabled by default.

    In order to enable this feature you have to follow the `setup
    instructions <controller_setup_who_is_lookup_>`_ below and then
    activate it via :ref:`global setting or from the admin interface
    <OPENWISP_CONTROLLER_WHO_IS_ENABLED>`.

WhoIs feature includes fetching details of the last public ip address
reported by a device to ensure better device management.

The fetched details include Organization Name, ASN, CIDR, Address,
Timezone.

.. _controller_setup_who_is_lookup:

Setup
-----

Ensure that your project ``settings.py`` contains the variables as
follows:

.. code-block:: python

    OPENWISP_CONTROLLER_GEOIP_ACCOUNT_ID = os.getenv(
        "OPENWISP_CONTROLLER_GEOIP_ACCOUNT_ID", ""
    )
    OPENWISP_CONTROLLER_GEOIP_LICENSE_KEY = os.getenv(
        "OPENWISP_CONTROLLER_GEOIP_LICENSE_KEY", ""
    )

Steps to obtain values of above settings
----------------------------------------

- Create Maxmind account using the following link: `Create Account
  <https://www.maxmind.com/en/geolite2/signup>`_.

  If you already have an account then click **Sign In**

- Go to `Manage License Keys` .. image::
  https://github.com/user-attachments/assets/0c2f693f-d2f5-4811-abd1-6148750380e9
- Generate a New license Key. Name it whatever you like .. image::
  https://github.com/user-attachments/assets/57df27bc-4f9d-4701-88bf-91e6b715e4a6
- Copy the *Account Id* and *License Key* and Paste it in the environment
  variables: **OPENWISP_CONTROLLER_GEOIP_ACCOUNT_ID** and
  **OPENWISP_CONTROLLER_GEOIP_LICENSE_KEY**.
