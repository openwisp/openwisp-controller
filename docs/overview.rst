OpenWISP Controller
===================

.. note::

  This is the latest version

OpenWISP Controller is a configuration manager that allows to automate several
networking tasks like adoption, provisioning, management VPN configuration,
X509 certificates automatic generation, revocation of x509 certificates and
a lot more features.

OpenWISP is not only an application designed for end users, but can also be
used as a framework on which custom network automation solutions can be built
on top of its building blocks.

Other popular building blocks that are part of the OpenWISP ecosystem are:

- `openwisp-monitoring <https://github.com/openwisp/openwisp-monitoring>`_:
  provides device status monitoring, collection of metrics, charts, alerts,
  possibility to define custom checks
- `openwisp-firmware-upgrader <https://github.com/openwisp/openwisp-firmware-upgrader>`_:
  automated firmware upgrades (single devices or mass network upgrades)
- `openwisp-radius <https://github.com/openwisp/openwisp-radius>`_:
  based on FreeRADIUS, allows to implement network access authentication systems like
  802.1x WPA2 Enterprise, captive portal authentication, Hotspot 2.0 (802.11u)
- `openwisp-network-topology <https://github.com/openwisp/openwisp-network-topology>`_:
  provides way to collect and visualize network topology data from
  dynamic mesh routing daemons or other network software (eg: OpenVPN);
  it can be used in conjunction with openwisp-monitoring to get a better idea
  of the state of the network
- `openwisp-ipam <https://github.com/openwisp/openwisp-ipam>`_:
  allows to manage the assignment of IP addresses used in the network
- `openwisp-notifications <https://github.com/openwisp/openwisp-notifications>`_:
  allows users to be aware of important events happening in the network.

**For a more complete overview of the OpenWISP modules and architecture**,
see the
`OpenWISP Architecture Overview
<https://openwisp.io/docs/general/architecture.html>`_.


.. toctree::
   :maxdepth: 1
   :glob:

   user/automatic-provisioning-of-subnets.rst
   user/device-groups.rst
   user/how-to-configure-push-updates.rst
   user/how-to-setup-vxlan-over-wireguard.rst
   user/how-to-setup-wireguard.rst
   user/notification-alerts.rst
   user/organization-limits.rst
   user/send-commands.rst
   user/templates-and-variables.rst
   user/zerotier.rst
   user/rest-api.rst
   user/settings.rst
   developer/developer-docs.rst
