Automating ZeroTier Tunnels
===========================

.. important::

    This guide assumes your OpenWrt firmware has the ``zerotier`` package
    installed. If this package is not present, you will need to install
    it.

.. raw:: html

    <p style="text-align: center">
      <iframe
        width="560"
        height="315"
        src="https://www.youtube.com/embed/VThvUHi-4l4?si=MI6Koda404IqPldw"
        title="OpenWISP ZeroTier"
        frameborder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        referrerpolicy="strict-origin-when-cross-origin"
        allowfullscreen>
      </iframe>
    </p>

Follow the procedure described below to set up `ZeroTier
<https://www.zerotier.com/>`_ tunnels on your devices.

.. include:: ../partials/shared-object.rst

.. contents:: **Table of Contents**:
    :depth: 2
    :local:

1. Configure Self-Hosted ZeroTier Network Controller
----------------------------------------------------

If you haven't already set up a self-hosted ZeroTier network controller on
your server, now is a good time to do so. You can start by simply
installing ZeroTier on your server from the `official website
<https://www.zerotier.com/download/>`_.

2. Create VPN Server Configuration for ZeroTier
-----------------------------------------------

1. Visit ``/admin/config/vpn/add/`` to add a new VPN server.
2. We will set **Name** of this VPN server ``ZeroTier`` and **Host** as
   ``my-zerotier-server.mydomain.com:9993`` (update this to point to your
   ZeroTier VPN server).
3. Select ``ZeroTier`` from the dropdown as **VPN Backend**.
4. When using ZeroTier, OpenWISP takes care of managing IP addresses
   (assigning an IP address to each VPN client (ZeroTier network
   members)). You can create a new subnet or select an existing one from
   the dropdown menu. You can also assign an **Internal IP** to the
   ZeroTier controller or leave it empty for OpenWISP to configure. This
   IP address will be used to assign it to the ZeroTier controller running
   on the server.
5. Set the **Webhook AuthToken**, this will be the ZeroTier authorization
   token which you can obtain by running the following command on the
   ZeroTier controller:

   .. code-block:: shell

       sudo cat /var/lib/zerotier-one/authtoken.secret

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/vpn-server-1.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/vpn-server-1.png
    :alt: ZeroTier VPN server configuration example 1

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/vpn-server-2.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/vpn-server-2.png
    :alt: ZeroTier VPN server configuration example 2

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/vpn-server-3.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/vpn-server-3.png
    :alt: ZeroTier VPN server configuration example 3

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/vpn-server-4.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/vpn-server-4.png
    :alt: ZeroTier VPN server configuration example 4

6. After clicking on **Save and continue editing**, OpenWISP automatically
   detects the node address of the ZeroTier controller and creates a
   ZeroTier network. The **network_id** of this network can be viewed in
   the **System Defined Variables** section, where it also provides
   internal IP address information.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/vpn-server-5.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/vpn-server-5.png
    :alt: ZeroTier VPN server configuration example 5

3. Create VPN Client Template for ZeroTier VPN Server
-----------------------------------------------------

1. Visit ``/admin/config/template/add/`` to add a new template.
2. Set ``ZeroTier Client`` as **Name** (you can set whatever you want) and
   select ``VPN-client`` as **type** from the dropdown list.
3. The **Backend** field refers to the backend of the device this template
   can be applied to. For this example, we will leave it to ``OpenWrt``.
4. Select the correct VPN server from the dropdown for the **VPN** field.
   Here it is ``ZeroTier``.
5. Ensure that the **Automatic tunnel provisioning** option is checked.
   This will enable OpenWISP to automatically provision an IP address and
   ZeroTier identity secrets (used for assigning member IDs) for each
   ZeroTier VPN client.
6. After clicking on **Save and continue editing** button, you will see
   details of *ZeroTier* VPN server in **System Defined Variables**. The
   template configuration will be automatically generated which you can
   tweak accordingly. We will use the automatically generated VPN client
   configuration for this example.

.. note::

    OpenWISP uses `zerotier-idtool
    <https://github.com/zerotier/ZeroTierOne/blob/dev/doc/zerotier-idtool.1.md>`_
    to manage **ZeroTier identity secrets**. Please make sure that you
    have `ZeroTier package installed
    <https://www.zerotier.com/download/>`_ on the server.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/template.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/template.png
    :alt: ZeroTier VPN client template example

4. Apply ZeroTier VPN Template to Devices
-----------------------------------------

.. note::

    This step assumes that you already have a device registered on
    OpenWISP. Register or create a device before proceeding.

1. Open the **Configuration** tab of the concerned device.
2. Select the *ZeroTier Client* template.
3. Upon clicking the **Save and Continue Editing** button, you will see
   entries in the **System Defined Variables** section. These entries will
   include **zerotier_member_id**, **identity_secret**, and the internal
   **IP address** of the ZeroTier client (network member) on the device,
   along with details of the VPN server.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/device-configuration-1.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/device-configuration-1.png
    :alt: ZeroTier VPN device configuration example 1

4. Once the configuration is successfully applied to the device, you will
   notice a new ZeroTier interface that is up and running. This interface
   will have the name ``owzt89f498`` (where ``owzt`` is followed by the
   last six hexadecimal characters of the ZeroTier **network ID**).

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/device-configuration-2.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/zerotier-tutorial/device-configuration-2.png
    :alt: ZeroTier VPN device configuration example 2

**Congratulations!** You've successfully configured OpenWISP to manage
ZeroTier tunnels on your devices.

.. seealso::

    You may also want to explore other automated VPN tunnel provisioning
    options:

    - :doc:`Wireguard </controller/user/wireguard>`
    - :doc:`Wireguard over VXLAN </controller/user/vxlan-wireguard>`
    - :doc:`OpenVPN </controller/user/openvpn>`
