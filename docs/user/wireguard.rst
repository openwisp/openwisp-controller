Automating WireGuard Tunnels
============================

.. important::

    This guide assumes your OpenWrt firmware has the ``wireguard-tools``
    package and its dependencies installed. If these packages are not
    present, you will need to install them.

This guide will help you to set up the automatic provisioning of
`WireGuard <https://www.wireguard.com/>`_ tunnels for your devices.

.. include:: ../partials/shared-object.rst

.. contents:: **Table of Contents**:
    :depth: 2
    :local:

1. Create VPN Server Configuration for WireGuard
------------------------------------------------

1. Visit ``/admin/config/vpn/add/`` to add a new VPN server.
2. Set the **Name** of this VPN server as ``WireGuard`` and the **Host**
   as ``wireguard-server.mydomain.com`` (update this to point to your
   WireGuard VPN server).
3. Select ``WireGuard`` from the dropdown as the **VPN Backend**.
4. When using WireGuard, OpenWISP takes care of managing IP addresses,
   assigning an IP address to each VPN peer. Create a new subnet or select
   an existing one from the dropdown menu. You can also assign an
   **Internal IP** to the WireGuard Server or leave it empty for OpenWISP
   to configure. This IP address will be used by the WireGuard interface
   on the server.
5. Set the **Webhook Endpoint** as
   ``https://wireguard-server.mydomain.com:8081/trigger-update`` for this
   example. Update this according to your VPN upgrader endpoint. Set
   **Webhook AuthToken** to any strong passphrase; this will be used to
   ensure that configuration upgrades are requested from trusted sources.

   .. note::

       If you are setting up a WireGuard VPN server, substitute
       ``wireguard-server.mydomain.com`` with the hostname of your VPN
       server and follow the steps in the next section.

6. Under the configuration section, set the name of the WireGuard tunnel 1
   interface. In this example, we have used ``wg0``.

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-tutorial/vpn-server-1.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-tutorial/vpn-server-1.png
    :alt: WireGuard VPN server configuration example 1

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-tutorial/vpn-server-2.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-tutorial/vpn-server-2.png
    :alt: WireGuard VPN server configuration example 2

7. After clicking on **Save and continue editing**, you will see that
   OpenWISP has automatically created public and private keys for the
   WireGuard server in **System Defined Variables**, along with internal
   IP address information.

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-tutorial/vpn-server-3.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-tutorial/vpn-server-3.png
    :alt: WireGuard VPN server configuration example 3

2. Deploy WireGuard VPN Server
------------------------------

If you haven't already set up WireGuard on your VPN server, this would be
a good time to do so.

We recommend using the `ansible-wireguard-openwisp
<https://github.com/openwisp/ansible-wireguard-openwisp>`_ role for
installing WireGuard, as it also installs scripts that allow OpenWISP to
manage the WireGuard VPN server.

Ensure that the VPN server attributes used in your playbook match the VPN
server configuration in OpenWISP.

3. Create VPN Client Template for WireGuard VPN Server
------------------------------------------------------

1. Visit ``/admin/config/template/add/`` to add a new template.
2. Set ``WireGuard Client`` as **Name** (you can set whatever you want)
   and select ``VPN-client`` as **type** from the dropdown list.
3. The **Backend** field refers to the backend of the device this template
   can be applied to. For this example, we will leave it to ``OpenWrt``.
4. Select the correct VPN server from the dropdown for the **VPN** field.
   Here it is ``WireGuard``.
5. Ensure that **Automatic tunnel provisioning** is checked. This will
   make OpenWISP to automatically generate public and private keys and
   provision IP address for each WireGuard VPN client.
6. After clicking on **Save and continue editing** button, you will see
   details of *WireGuard* VPN server in **System Defined Variables**. The
   template configuration will be automatically generated which you can
   tweak accordingly. We will use the automatically generated VPN client
   configuration for this example.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-tutorial/template.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-tutorial/template.png
    :alt: WireGuard VPN client template example

4. Apply WireGuard VPN Template to Devices
------------------------------------------

.. note::

    This step assumes that you already have a device registered on
    OpenWISP. Register or create a device before proceeding.

1. Open the **Configuration** tab of the concerned device.
2. Select the *WireGuard Client* template.
3. Upon clicking on **Save and continue editing** button, you will see
   some entries in **System Defined Variables**. It will contain internal
   IP address, private and public key for the WireGuard client on the
   device along with details of WireGuard VPN server.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-tutorial/device-configuration.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-tutorial/device-configuration.png
    :alt: WireGuard VPN device configuration example

**Voila!** You have successfully configured OpenWISP to manage WireGuard
tunnels for your devices.

.. seealso::

    You may also want to explore other automated VPN tunnel provisioning
    options:

    - :doc:`Wireguard over VXLAN </controller/user/vxlan-wireguard>`
    - :doc:`Zerotier </controller/user/zerotier>`
    - :doc:`OpenVPN </controller/user/openvpn>`
