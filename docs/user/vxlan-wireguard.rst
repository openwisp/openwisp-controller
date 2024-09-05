Automating VXLAN over WireGuard Tunnels
=======================================

.. important::

    This guide assumes your OpenWrt firmware has the ``vxlan`` and
    ``wireguard-tools`` packages installed. If these packages are not
    present, you will need to install them.

By following these steps, you will be able to setup layer 2 VXLAN tunnels
encapsulated in `WireGuard <https://www.wireguard.com/>`_ tunnels which
work on layer 3.

.. include:: ../partials/shared-object.rst

.. contents:: **Table of Contents**:
    :depth: 2
    :local:

1. Create VPN Server Configuration for VXLAN Over WireGuard
-----------------------------------------------------------

1. Visit ``/admin/config/vpn/add/`` to add a new VPN server.
2. We will set **Name** of this VPN server ``Wireguard VXLAN`` and
   **Host** as ``wireguard-vxlan-server.mydomain.com`` (update this to
   point to your WireGuard VXLAN VPN server).
3. Select ``VXLAN over WireGuard`` from the dropdown as **VPN Backend**.
4. When using VXLAN over WireGuard, OpenWISP takes care of managing IP
   addresses (assigning an IP address to each VPN peer). You can create a
   new subnet or select an existing one from the dropdown menu. You can
   also assign an **Internal IP** to the WireGuard Server or leave it
   empty for OpenWISP to configure. This IP address will be used by the
   WireGuard interface on server.
5. We have set the **Webhook Endpoint** as
   ``https://wireguard-vxlan-server.mydomain.com:8081/trigger-update`` for
   this example. You will need to update this according to you VPN
   upgrader endpoint. Set **Webhook AuthToken** to any strong passphrase,
   this will be used to ensure that configuration upgrades are requested
   from trusted sources.

.. note::

    If you are following this tutorial for also setting up WireGuard VPN
    server, just substitute ``wireguard-server.mydomain.com`` with
    hostname of your VPN server and follow the steps in next section.

6. Under the configuration section, set the name of WireGuard tunnel 1
   interface. We have used ``wg0`` in this example.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-vxlan-tutorial/vpn-server-1.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-vxlan-tutorial/vpn-server-1.png
    :alt: WireGuard VPN VXLAN server configuration example 1

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-vxlan-tutorial/vpn-server-2.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-vxlan-tutorial/vpn-server-2.png
    :alt: WireGuard VPN VXLAN server configuration example 2

7. After clicking on **Save and continue editing**, you will see that
   OpenWISP has automatically created public and private key for WireGuard
   server in **System Defined Variables** along with internal IP address
   information.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-vxlan-tutorial/vpn-server-3.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-vxlan-tutorial/vpn-server-3.png
    :alt: WireGuard VXLAN VPN server configuration example 3

2. Deploy Wireguard VXLAN VPN Server
------------------------------------

If you haven't already set up WireGuard on your VPN server, this is a good
time to do so. We recommend using the `ansible-wireguard-openwisp
<https://github.com/openwisp/ansible-wireguard-openwisp>`_ role for
installing WireGuard since it also installs scripts that allow OpenWISP to
manage the WireGuard VPN server along with VXLAN tunnels.

Pay attention to the VPN server attributes used in your playbook. It
should be the same as the VPN server configuration in OpenWISP.

3. Create VPN Client Template for WireGuard VXLAN VPN Server
------------------------------------------------------------

1. Visit ``/admin/config/template/add/`` to add a new template.
2. Set ``Wireguard VXLAN Client`` as **Name** (you can set whatever you
   want) and select ``VPN-client`` as **type** from the dropdown list.
3. The **Backend** field refers to the backend of the device this template
   can be applied to. For this example, we will leave it as ``OpenWrt``.
4. Select the correct VPN server from the dropdown for the **VPN** field.
   Here it is ``Wireguard VXLAN``.
5. Ensure that **Automatic tunnel provisioning** is checked. This will
   make OpenWISP automatically generate public and private keys and
   provision IP addresses for each WireGuard VPN client along with the
   VXLAN Network Identifier (VNI).
6. After clicking on **Save and continue editing** button, you will see
   details of the *Wireguard VXLAN* VPN server in **System Defined
   Variables**. The template configuration will be automatically generated
   which you can tweak accordingly. We will use the automatically
   generated VPN client configuration for this example.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-vxlan-tutorial/template.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-vxlan-tutorial/template.png
    :alt: WireGuard VXLAN VPN client template example

4. Apply Wireguard VXLAN VPN Template to Devices
------------------------------------------------

.. note::

    This step assumes that you already have a device registered on
    OpenWISP. Register or create a device before proceeding.

1. Open the **Configuration** tab of the concerned device.
2. Select the *WireGuard VXLAN Client* template.
3. Upon clicking on **Save and continue editing** button, you will see
   some entries in **System Defined Variables**. It will contain internal
   IP address, private and public key for the WireGuard client on the
   device and details of WireGuard VPN server along with VXLAN Network
   Identifier(VNI) of this device.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-vxlan-tutorial/device-configuration.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/wireguard-vxlan-tutorial/device-configuration.png
    :alt: WireGuard VXLAN VPN device configuration example

**Voila!** You have successfully configured OpenWISP to manage VXLAN over
WireGuard tunnels for your devices.

.. seealso::

    You may also want to explore other automated VPN tunnel provisioning
    options:

    - :doc:`Wireguard </controller/user/wireguard>`
    - :doc:`Zerotier </controller/user/zerotier>`
    - :doc:`OpenVPN </controller/user/openvpn>`
