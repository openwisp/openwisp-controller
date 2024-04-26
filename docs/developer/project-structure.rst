Project Structure & main features
----------------------------------

.. include:: /partials/developers-docs-warning.rst

OpenWISP Controller is a python package consisting of four django apps:

Config App
~~~~~~~~~~

* **configuration management** for embedded devices supporting different firmwares:
    - `OpenWRT <http://openwrt.org>`_
    - `OpenWISP Firmware <https://github.com/openwisp/OpenWISP-Firmware>`_
    - support for additional firmware can be added by `specifying custom backends <#netjsonconfig-backends>`_
* **configuration editor** based on `JSON-Schema editor <https://github.com/jdorn/json-editor>`_
* **advanced edit mode**: edit `NetJSON  <http://netjson.org>`_ *DeviceConfiguration* objects for maximum flexibility
* `configuration templates <https://openwisp.io/docs/user/templates.html>`_:
  reduce repetition to the minimum, configure default and required templates
* `configuration variables <#how-to-use-configuration-variables>`_:
  reference ansible-like variables in the configuration and templates
* **template tags**: tag templates to automate different types of auto-configurations (eg: mesh, WDS, 4G)
* **device groups**: add `devices to dedicated groups <#device-groups>`_ to
  ease management of group of devices
* **simple HTTP resources**: allow devices to automatically download configuration updates
* **VPN management**: `automatically provision VPN tunnels <#openwisp-controller-default-auto-cert>`_,
  including cryptographic keys, IP addresses
* `REST API <#rest-api-reference>`_
* `Export/Import devices <#>`_

PKI App
~~~~~~~

The PKI app is based on `django-x509 <https://github.com/openwisp/django-x509>`_,
it allows to create, import and view x509 CAs and certificates directly from
the administration dashboard, it also adds different endpoints to the
`REST API <#rest-api-reference>`_.

Connection App
~~~~~~~~~~~~~~

This app allows OpenWISP Controller to use different protocols to reach network devices.
Currently, the default connnection protocols are SSH and SNMP, but the protocol
mechanism is extensible and more protocols can be implemented if needed.

SSH
###

The SSH connector allows the controller to initialize connections to the devices
in order perform `push operations <#how-to-configure-push-updates>`__:

- Sending configuration updates.
- `Executing shell commands <#sending-commands-to-devices>`_.
- Perform `firmware upgrades via the additional firmware upgrade module <https://github.com/openwisp/openwisp-firmware-upgrader>`_.
- `REST API <#rest-api-reference>`_

The default connection protocol implemented is SSH, but other protocol
mechanism is extensible and custom protocols can be implemented as well.

Access via SSH key is recommended, the SSH key algorithms supported are:

- RSA
- Ed25519

SNMP
####

The SNMP connector is useful to collect monitoring information and it's used in
`openwisp-monitoring`_ for performing checks to collect monitoring information.
`Read more <https://github.com/openwisp/openwisp-monitoring/pull/309#discussion_r692566202>`_ on how to use it.

Geo App
~~~~~~~

The geographic app is based on `django-loci <https://github.com/openwisp/django-loci>`_
and allows to define the geographic coordinates of the devices,
as well as their indoor coordinates on floorplan images.

It also adds different endpoints to the `REST API <#rest-api-reference>`_.

Subnet Division App
~~~~~~~~~~~~~~~~~~~

This app allows to automatically provision subnets and IP addresses which will be
available as `system defined configuration variables <#system-defined-variables>`_
that can be used in templates. The purpose of this app is to allow users to automatically
provision and configure specific
subnets and IP addresses to the devices without the need of manual intervention.

Refer to `"How to configure automatic provisioning of subnets and IPs"
section of this documentation
<#how-to-configure-automatic-provisioning-of-subnets-and-ips>`_
to learn about features provided by this app.

This app is optional, if you don't need it you can avoid adding it to
``settings.INSTALLED_APPS``.

