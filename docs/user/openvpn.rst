Automating OpenVPN Tunnels
==========================

.. important::

    This guide assumes your OpenWrt firmware has the ``openvpn-mbedtls``
    package (or equivalent versions like ``openvpn-wolfssl`` or
    ``openvpn-openssl``) installed. If this package is not present, you
    will need to install it.

In this guide, we will explore how to set up the automatic provisioning
and management of **OpenVPN tunnels**.

.. contents:: **Table of Contents**:
    :backlinks: none
    :depth: 3

Setting up the OpenVPN Server
-----------------------------

The first step is to install the OpenVPN server. In this tutorial, to
perform this step we will use Ansible.

If you already have experience installing an OpenVPN server, feel free to
use any method you prefer.

.. important::

    If you have already set up your OpenVPN server or prefer to install
    the OpenVPN server using a different method, you can skip forward to
    :ref:`import_ca_and_server_cert`.

For simplicity, **the OpenVPN server must be installed on the same server
where OpenWISP is also installed**.

While it is possible to install the OpenVPN server on a different server,
it requires additional steps not covered in this tutorial.

1. Install Ansible and Required Ansible Roles
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install Ansible **on your local machine** (please ensure that you do not
install it on the server).

To **install Ansible**, we suggest following the official `Ansible
installation guide
<http://docs.ansible.com/ansible/latest/intro_installation.html>`_.

After installing Ansible, you need to install Git (example for Linux
Debian/Ubuntu systems):

.. code-block:: bash

    sudo apt-get install git

After installing both Ansible and Git, install the required roles:

.. code-block:: bash

    ansible-galaxy install git+https://github.com/Stouts/Stouts.openvpn,3.0.0 nkakouros.easyrsa

2. Create Inventory File and Playbook YAML
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create an Ansible inventory file named ``inventory`` **on your local
machine** (not on the server) with the following contents:

.. code-block::

    [openvpn]
    your_server_domain_or_ip

For example, if your server IP is ``192.168.56.2``:

.. code-block::

    [openvpn]
    192.168.56.2

In the same directory where you created the ``inventory`` file, create a
file named ``playbook.yml`` with the following content:

.. code-block:: yaml

    - hosts: openvpn
      vars:
        # EasyRSA
        easyrsa_generate_dh: true
        easyrsa_servers:
          - name: server
        easyrsa_clients: []
        easyrsa_pki_dir: /etc/easyrsa/pki

        # OpenVPN
        openvpn_keydir: "{{ easyrsa_pki_dir }}"
        openvpn_clients: []
        openvpn_use_pam: false
      roles:
        - role: nkakouros.easyrsa
        - role: Stouts.openvpn

.. hint::

    You can further customize the configuration using the role variables.
    Read more about other options in `EasyRSA
    <https://github.com/nkakouros-original/ansible-role-easyrsa>`_ and
    `OpenVPN <https://github.com/Stouts/Stouts.openvpn>`_.

3. Run the Playbook
~~~~~~~~~~~~~~~~~~~

Run the Ansible playbook:

.. code-block:: bash

    ansible-playbook -i inventory playbook.yml -b -k -K --become-method=su

.. _import_ca_and_server_cert:

Import the CA and the Server Certificate in OpenWISP
----------------------------------------------------

.. important::

    If you chose an alternative installation method for OpenVPN and you
    did not create the CA and certificate yet, you can create the
    certificates from scratch via the OpenWISP web interface instead of
    importing them.

    Follow the instructions below and instead of selecting
    :guilabel:`Import Existing` as :guilabel:`Operation Type`, select
    :guilabel:`Create new`.

    You also won't need to copy any file from the server as OpenWISP
    generates the x509 certificates automatically.

To import the CA and Server Certificate into OpenWISP, you need to access
your server via ``ssh`` or any other method that suits you.

Change your directory to ``/etc/easyrsa/pki/``.

.. note::

    If you incur in the following error: ``-bash: cd: /etc/easyrsa/pki:
    Permission denied``, you may need to log in as the root user.

Import the CA
~~~~~~~~~~~~~

In your OpenWISP dashboard, go to ``/admin/pki/ca/add/``.

In :guilabel:`Operation Type`, choose :guilabel:`Import Existing`.

Get your CA certificate from the ``ca.crt`` file and the private key from
the ``private/ca.key`` file, then enter them in the respective fields.

Import the Server Certificate
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In your OpenWISP dashboard, go to ``/admin/pki/cert/add/``.

In :guilabel:`Operation Type`, choose :guilabel:`Import Existing` and in
**CA**, choose the CA you just created.

Get your server certificate from the ``issued/server.crt`` file and the
server private key from the ``private/server.key`` file, then enter them
in the respective fields.

Create the VPN Server in OpenWISP
---------------------------------

In the OpenWISP dashboard, go to ``/admin/config/vpn/add/``.

In the :guilabel:`Host` field, enter your server IP address. In the
:guilabel:`Certification Authority` and :guilabel:`X509 Certificate`
fields, select the CA and certificate you created in the previous step.

Under :guilabel:`Configuration`, click on :guilabel:`Configuration Menu`,
then change :guilabel:`Server (Bridged)` to :guilabel:`Server (Routed)`.

Setting up a Bridged Server is similar to setting up a Routed Server but
is not covered in this tutorial.

Adjust the rest of the VPN configuration to match the settings in
``/etc/openvpn/server.conf``.

.. tip::

    You can verify if your VPN configuration matches the ``server.conf``
    file by using the :guilabel:`Preview Configuration` button at the top
    right corner of the page.

Create the VPN-Client Template in OpenWISP
------------------------------------------

In your OpenWISP dashboard, go to ``/admin/config/template/add/``.

Set the :guilabel:`Type` to :guilabel:`VPN-client`.

Once the :guilabel:`VPN` field appears, select the VPN you created in the
previous step.

Ensure the :guilabel:`Automatic tunnel provisioning` flag remains enabled.

If this template is for your management VPN or the default VPN option, we
recommend checking the :guilabel:`Enabled by default` flag. For more
information about this flag, refer to :ref:`default_templates`.

Now, save the template.

After saving the template, you can tweak the VPN Client configuration,
which is automatically generated to be compatible with the server
configuration.

Finally you can add the new template to your devices.

.. tip::

    If you need to troubleshoot any issue, increase the verbosity of the
    OpenVPN logging, both on the server and the clients, and check both
    logs (on the server and on the client).

.. seealso::

    You may also want to explore other automated VPN tunnel provisioning
    options:

    - :doc:`Wireguard </controller/user/wireguard>`
    - :doc:`Wireguard over VXLAN </controller/user/vxlan-wireguard>`
    - :doc:`Zerotier </controller/user/zerotier>`
