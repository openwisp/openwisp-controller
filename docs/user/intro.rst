Controller: Structure & Features
================================

OpenWISP Controller is a Python package which ships five Django apps.

.. contents:: **These Django apps are listed below**:
    :depth: 1
    :local:

Config App
----------

The config app is the core of the controller module and implements all the
following features:

- **Configuration management** for embedded devices supporting:
      - `OpenWrt <http://openwrt.org>`_
      - `OpenWISP Firmware
        <https://github.com/openwisp/OpenWISP-Firmware>`_
      - additional firmware can be added by :ref:`specifying custom
        configuration backends <OPENWISP_CONTROLLER_BACKENDS>`
- **Configuration editor** based on `JSON-Schema editor
  <https://github.com/jdorn/json-editor>`_
- **Advanced edit mode**: edit `NetJSON <http://netjson.org>`_
  *DeviceConfiguration* objects for maximum flexibility
- :doc:`templates`: reduce repetition to the minimum, configure default
  and required templates
- :doc:`variables`: reference variables in the configuration and templates
- :doc:`device-groups`: define different set of default configuration and
  metadata in device groups
- :ref:`Template Tags <templates_tags>`: define different sets of default
  templates (e.g.: mesh, WDS, 4G)
- **HTTP resources**: allow devices to automatically check for and
  download configuration updates
- **VPN management**: automatically provision VPN tunnel configurations,
  including cryptographic keys and IP addresses, e.g.: :doc:`OpenVPN
  </user/vpn>`, :doc:`WireGuard <wireguard>`
- :doc:`whois`: display information about the public IP address used by
  devices to communicate with OpenWISP
- :doc:`import-export`

It exposes various :doc:`REST API endpoints <rest-api>`.

PKI App
-------

The PKI app is based on `django-x509
<https://github.com/openwisp/django-x509>`_, allowing you to create,
import, and view x509 CAs and certificates directly from the
administration dashboard.

It exposes various :doc:`REST API endpoints <rest-api>`.

Connection App
--------------

This app enables OpenWISP Controller to use different protocols to reach
network devices. Currently, the default connection protocols are SSH and
SNMP, but the protocol mechanism is extensible, allowing for
implementation of additional protocols if needed.

It exposes various :doc:`REST API endpoints <rest-api>`.

SSH
~~~

The SSH connector allows the controller to initialize connections to the
devices in order to perform :doc:`push operations <push-operations>`,
e.g.:

- Sending configuration updates.
- :doc:`Executing shell commands <shell-commands>`.
- Perform firmware upgrades via the additional :doc:`firmware upgrade
  module </firmware-upgrader/index>`.

The default connection protocol implemented is SSH, but other protocol
mechanism is extensible and custom protocols can be implemented as well.

Access via SSH key is recommended, the SSH key algorithms supported are:

- RSA
- Ed25519

SNMP
~~~~

The SNMP connector is useful to collect monitoring information and it's
used in :doc:`OpenWISP Monitoring </monitoring/index>` for performing
checks to collect monitoring information. `Read more
<https://github.com/openwisp/openwisp-monitoring/pull/309#discussion_r692566202>`_
on how to use it.

Geo App
-------

The geographic app is based on `django-loci
<https://github.com/openwisp/django-loci>`_ and allows to define the
geographic coordinates of the devices, as well as their indoor coordinates
on floor plan images.

It also provides an :doc:`estimated-location` feature which automatically
creates or updates device locations based on WHOIS data.

It exposes various :doc:`REST API endpoints <rest-api>`.

Subnet Division App
-------------------

.. note::

    This app is optional, if you don't need it you can avoid adding it to
    ``settings.INSTALLED_APPS``.

This app allows to automatically provision subnets and IP addresses which
will be available as :ref:`system defined configuration variables
<system_defined_variables>` that can be used in :doc:`templates`.

The purpose of this app is to allow users to automatically provision and
configure specific subnets and IP addresses to the devices without the
need of manual intervention.

Refer to :doc:`subnet-division-rules` for more information.
