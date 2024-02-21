How to configure automatic provisioning of subnets and IPs
----------------------------------------------------------

The following steps will help you configure automatic provisioning of subnets and IPs
for devices.

1. Create a Subnet and a Subnet Division Rule
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a master subnet under which automatically generated subnets will be provisioned.

**Note**: Choose the size of the subnet appropriately considering your use case.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/subnet.png
  :alt: Creating a master subnet example

On the same page, add a **subnet division rule** that will be used to provision subnets
under the master subnet.

The type of subnet division rule controls when subnets and IP addresses will be provisioned
for a device. The subnet division rule types currently implemented are described below.

Device Subnet Division Rule
###########################

This rule type is triggered whenever a device configuration (``config.Config`` model)
is created for the organization specified in the rule.

Creating a new rule of ^Device^ type will also provision subnets and
IP addresses for existing devices of the organization automatically.

**Note**: a device without a configuration will not trigger this rule.

VPN Subnet Division Rule
########################

This rule is triggered when a VPN client template is assigned to a device,
provided the VPN server to which the VPN client template relates to has
the same subnet for which the subnet division rule is created.

**Note:** This rule will only work for **WireGuard** and **VXLAN over WireGuard**
VPN servers.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/subnet-division-rule.png
  :alt: Creating a subnet division rule example

In this example, **VPN subnet division rule** is used.

2. Create a VPN Server
~~~~~~~~~~~~~~~~~~~~~~

Now create a VPN Server and choose the previously created **master subnet** as the subnet for
this VPN Server.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/vpn-server.png
  :alt: Creating a VPN Server example

3. Create a VPN Client Template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a template, setting the **Type** field to **VPN Client** and **VPN** field to use the
previously created VPN Server.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/vpn-client.png
  :alt: Creating a VPN Client template example

**Note**: You can also check the **Enable by default** field if you want to automatically
apply this template to devices that will register in future.

4. Apply VPN Client Template to Devices
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With everything in place, you can now apply the VPN Client Template to devices.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/apply-template-to-device.png
  :alt: Adding template to device example

After saving the device, you should see all provisioned Subnets and IPs for this device
under `System Defined Variables <~system-defined-variables>`_.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/subnet-division-rule/system-defined-variables.png
  :alt: Provisioned Subnets and IPs available as System Defined Variables example

Voila! You can now use these variables in configuration of the device. Refer to `How to use configuration variables <~how-to-use-configuration-variables>`_
section of this documentation to learn how to use configuration variables.

Important notes for using Subnet Division
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- In the above example Subnet, VPN Server, and VPN Client Template belonged to the **default** organization.
  You can use **Systemwide Shared** Subnet, VPN Server, or VPN Client Template too, but
  Subnet Division Rule will be always related to an organization. The Subnet Division Rule will only be
  triggered when such VPN Client Template will be applied to a Device having the same organization as Subnet Division Rule.

- You can also use the configuration variables for provisioned subnets and IPs in the Template.
  Each variable will be resolved differently for different devices. E.g. ``OW_subnet1_ip1`` will resolve to
  ``10.0.0.1`` for one device and ``10.0.0.55`` for another. Every device gets its own set of subnets and IPs.
  But don't forget to provide the default fall back values in the ^default values^ template field
  (used mainly for validation).

- The Subnet Division Rule will automatically create a reserved subnet, this subnet can be used
  to provision any IP addresses that have to be created manually. The rest of the master subnet
  address space **must not** be interfered with or the automation implemented in this module
  will not work.

- The above example used `VPN subnet division rule <~vpn-subnet-division-rule>`_. Similarly,
  `device subnet division rule <~device-subnet-division-rule>`_ can be used, which only requires
  `creating a subnet and a subnet division rule <~1-create-a-subnet-and-a-subnet-division-rule>`_.

Limitations of Subnet Division
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the current implementation, it is not possible to change ^Size^, ^Number of Subnets^ and
^Number of IPs^ fields of an existing subnet division rule due to following reasons:

Size
####

Allowing to change size of provisioned subnets of an existing subnet division rule
will require rebuilding of Subnets and IP addresses which has possibility of breaking
existing configurations.

Number of Subnets
#################

Allowing to decrease number of subnets of an existing subnet division
rule can create patches of unused subnets dispersed everywhere in the master subnet.
Allowing to increase number of subnets will break the continuous allocation of subnets for
every device. It can also break configuration of devices.

Number of IPs
#############

Allowing to decrease number of IPs of an existing subnet division rule
will lead to deletion of IP Addresses which can break configuration of devices being used.
It **is allowed** to increase number of IPs.

If you want to make changes to any of above fields, delete the existing rule and create a
new one. The automation will provision for all existing devices that meets the criteria
for provisioning. **WARNING**: It is possible that devices get different subnets and IPs
from previous provisioning.
