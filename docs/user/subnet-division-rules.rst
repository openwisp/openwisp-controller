Automating Subnet and IP Address Provisioning
=============================================

This guide helps you automate provisioning subnets and IP addresses for
your network devices.

.. contents:: **Table of Contents**:
    :depth: 2
    :local:

.. _step1_rule:

1. Create a Subnet and a Subnet Division Rule
---------------------------------------------

Create a master subnet.

This is the parent subnet from which automatically generated subnets will
be provisioned.

.. note::

    Choose a subnet size appropriate for the needs of your network.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/subnet.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/subnet.png
    :alt: Creating a master subnet example

On the same page, add a **subnet division rule**. This rule defines the
criteria for automatically provisioning subnets under the master subnet.

The type of subnet division rule determines when subnets and IP addresses
are assigned to devices.

The currently supported rule types are described below.

.. note::

    For information on how to write your own subnet division rule types,
    please refer to: :ref:`custom_subnet_division_rule_types`.

.. _device_rule:

Device Subnet Division Rule
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This rule triggers when a device configuration (``config.Config`` model)
is created for the organization specified in the rule.

.. note::

    If a device object is created without any related configuration
    object, it will not trigger this rule.

Creating a new *"Device"* rule will also automatically provision subnets
and IP addresses for existing devices within the organization.

.. _vpn_rule:

VPN Subnet Division Rule
~~~~~~~~~~~~~~~~~~~~~~~~

This rule triggers when a template flagged as *VPN-client* is assigned to
a device configuration, but only if the VPN server associated with the
VPN-client template uses the same subnet to which the subnet division rule
is assigned to.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/subnet-division-rule.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/subnet-division-rule.png
    :alt: Creating a subnet division rule example

In this example, **VPN subnet division rule** is used.

2. Create a VPN Server
----------------------

Now create a VPN Server and choose the previously created **master
subnet** as the subnet for this VPN Server.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/vpn-server.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/vpn-server.png
    :alt: Creating a VPN Server example

3. Create a VPN Client Template
-------------------------------

Create a template, setting the **Type** field to **VPN Client** and
**VPN** field to use the previously created VPN Server.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/vpn-client.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/vpn-client.png
    :alt: Creating a VPN Client template example

.. note::

    You can also check the **Enable by default** field if you want to
    automatically apply this template to devices that will register in
    future.

4. Apply VPN Client Template to Devices
---------------------------------------

With everything in place, you can now apply the VPN Client Template to
devices.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/apply-template-to-device.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/apply-template-to-device.png
    :alt: Adding template to device example

After saving the device, you should see all provisioned Subnets and IPs
for this device under :ref:`System Defined Variables
<system_defined_variables>`.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/system-defined-variables.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/system-defined-variables.png
    :alt: Provisioned Subnets and IPs available as System Defined Variables example

You can now use these :doc:`variables` in the configuration of devices of
your network.

Important notes for using Subnet Division
-----------------------------------------

- In the example provided, the Subnet, VPN Server, and VPN Client Template
  were associated with the **default** organization. You can also utilize
  **Systemwide Shared** Subnet, VPN Server, or VPN Client Template;
  however, remember that the Subnet Division Rule will always be linked to
  an organization. It will only be triggered when a VPN Client Template is
  applied to a Device with the same organization as the Subnet Division
  Rule.
- Configuration variables can be used for provisioned subnets and IPs in
  the Template. Each variable will resolve differently for different
  devices. For example, ``OW_subnet1_ip1`` will resolve to ``10.0.0.1``
  for one device and ``10.0.0.55`` for another. Every device receives its
  own set of subnets and IPs. Ensure to provide default fallback values in
  the *default values* template field (mainly used for validation).
- The Subnet Division Rule automatically creates a reserved subnet, which
  can be utilized to provision any IP addresses that need to be created
  manually. The remaining address space of the master subnet must not be
  interfered with, or the automation implemented in this module will not
  function.
- The example provided used the :ref:`VPN subnet division rule
  <vpn_rule>`. Similarly, the :ref:`device subnet division rule
  <device_rule>` can be employed, requiring only :ref:`the creation of a
  subnet and a subnet division rule <step1_rule>`.

Limitations of Subnet Division Rules
------------------------------------

In the current implementation, it is not possible to change *Size*,
*Number of Subnets* and *Number of IPs* fields of an existing subnet
division rule due to following reasons:

Size
~~~~

Allowing to change size of provisioned subnets of an existing subnet
division rule will require rebuilding of Subnets and IP addresses which
has possibility of breaking existing configurations.

Number of Subnets
~~~~~~~~~~~~~~~~~

Allowing to decrease number of subnets of an existing subnet division rule
can create patches of unused subnets dispersed everywhere in the master
subnet. Allowing to increase number of subnets will break the continuous
allocation of subnets for every device. It can also break configuration of
devices.

Number of IPs
~~~~~~~~~~~~~

**Decreasing the number of IPs** in an existing subnet division rule is
not allowed as it can lead to deletion of IP addresses, potentially
breaking configurations of existing devices.

**Increasing the number of IPs is allowed**.

If you need to modify any of these fields (**Size**, **Number of
Subnets**, or **Number of IPs**), we recommend to proceed as follows:

1. Delete the existing rule.
2. Create a new rule.

The automation will provision new subnets and addresses according to the
new parameters to any existing devices that are eligible to the subnet
division rule.

However, be aware that existing devices **will probably be reassigned
different subnets and IP addresses** than the ones used previously.
