Configuring Push Operations
===========================

.. important::

    If you have installed OpenWISP with the `ansbile-openwisp2 role
    <https://galaxy.ansible.com/openwisp/openwisp2>`_ you can skip the following steps,
    which are handled automatically by the ansible role during the first installation.

The Ansible role automatically creates a default template to update ``authorized_keys``
on networking devices using the default access credentials.

Follow the procedure described below to enable secure SSH access from OpenWISP to your
devices, this is required to enable push operations (whenever the configuration is
changed, OpenWISP will trigger the update in the background) and/or :doc:`firmware
upgrades (via the additional module openwisp-firmware-upgrader)
<../../../openwisp-firmware-upgrader/docs/index>`.

1. Generate SSH key
-------------------

First of all, we need to generate the SSH key which will be used by OpenWISP to access
the devices, to do so, you can use the following command:

.. code-block:: shell

    echo './sshkey' | ssh-keygen -t ed25519 -C "openwisp"

This will create two files in the current directory, one called ``sshkey`` (the private
key) and one called ``sshkey.pub`` (the public key).

Store the content of these files in a secure location.

**Note:** Support for **ED25519** was added in OpenWrt 21.02 (requires Dropbear >
2020.79). If you are managing devices with OpenWrt < 21, then you will need to use RSA
keys:

.. code-block:: shell

    echo './sshkey' | ssh-keygen -t rsa -b 4096 -C "openwisp"

2. Save SSH private key in OpenWISP (access credentials)
--------------------------------------------------------

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/add-ssh-credentials-private-key.png
    :alt: add SSH private key as access credential in OpenWISP

From the first page of OpenWISP click on "Access credentials", then click on the **"ADD
ACCESS CREDENTIALS"** button in the upper right corner (alternatively, go to the
following URL: ``/admin/connection/credentials/add/``).

Select SSH as ``type``, enable the **Auto add** checkbox, then at the field "Credentials
type" select "SSH (private key)", now type "root" in the ``username`` field, while in
the ``key`` field you have to paste the contents of the private key just created.

Now hit save.

The credentials just created will be automatically enabled for all the devices in the
system (both existing devices and devices which will be added in the future).

3. Add the public key to your devices
-------------------------------------

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/add-authorized-ssh-keys-template.png
    :alt: Add authorized SSH public keys template to OpenWISP (OpenWRT)

Now we need to instruct your devices to allow OpenWISP accessing via SSH, in order to do
this we need to add the contents of the public key file created in step 1
(``sshkey.pub``) in the file ``/etc/dropbear/authorized_keys`` on the devices, the
recommended way to do this is to create a configuration template in OpenWISP: from the
first page of OpenWISP, click on "Templates", then and click on the **"ADD TEMPLATE"**
button in the upper right corner (alternatively, go to the following URL:
``/admin/config/template/add/``).

Check **enabled by default**, then scroll down the configuration section, click on
"Configuration Menu", scroll down, click on "Files" then close the menu by clicking
again on "Configuration Menu". Now type ``/etc/dropbear/authorized_keys`` in the
``path`` field of the file, then paste the contents of ``sshkey.pub`` in ``contents``.

Now hit save.

**There's a catch**: you will need to assign the template to any existing device.

4. Test it
----------

Once you have performed the 3 steps above, you can test it as follows:

1. Ensure there's at least one device turned on and connected to OpenWISP, ensure this
   device has the "SSH Authorized Keys" assigned to it.
2. Ensure the celery worker of OpenWISP Controller is running (eg: ``ps aux | grep
   celery``)
3. SSH into the device and wait (maximum 2 minutes) until
   ``/etc/dropbear/authorized_keys`` appears as specified in the template.
4. While connected via SSH to the device run the following command in the console:
   ``logread -f``, now try changing the device name in OpenWISP
5. Shortly after you change the name in OpenWISP, you should see some output in the SSH
   console indicating another SSH access and the configuration update being performed.
