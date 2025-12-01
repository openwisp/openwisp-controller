Developer Installation Instructions
===================================

.. include:: ../partials/developer-docs.rst

.. contents:: **Table of Contents**:
    :depth: 2
    :local:

Dependencies
------------

- Python >= 3.9
- OpenSSL

Installing for Development
--------------------------

Install the system dependencies:

.. code-block:: shell

    sudo apt update
    sudo apt install -y sqlite3 libsqlite3-dev openssl libssl-dev
    sudo apt install -y gdal-bin libproj-dev libgeos-dev libspatialite-dev libsqlite3-mod-spatialite
    sudo apt install -y chromium-browser

Fork and clone the forked repository:

.. code-block:: shell

    git clone git://github.com/<your_fork>/openwisp-controller

Navigate into the cloned repository:

.. code-block:: shell

    cd openwisp-controller/

Launch Redis:

.. code-block:: shell

    docker compose up -d redis

Setup and activate a virtual-environment (we'll be using `virtualenv
<https://pypi.org/project/virtualenv/>`_):

.. code-block:: shell

    python -m virtualenv env
    source env/bin/activate

Make sure that your base python packages are up to date before moving to
the next step:

.. code-block:: shell

    pip install -U pip wheel setuptools

Install development dependencies:

.. code-block:: shell

    pip install -e .
    pip install -r requirements-test.txt
    sudo npm install -g prettier

Install WebDriver for Chromium for your browser version from
https://chromedriver.chromium.org/home and Extract ``chromedriver`` to one
of directories from your ``$PATH`` (example: ``~/.local/bin/``).

Create database:

.. code-block:: shell

    cd tests/
    ./manage.py migrate
    ./manage.py createsuperuser

Launch celery worker (for background jobs):

.. code-block:: shell

    celery -A openwisp2 worker -l info

Launch development server:

.. code-block:: shell

    ./manage.py runserver 0.0.0.0:8000

You can access the admin interface at ``http://127.0.0.1:8000/admin/``.

Run tests with (make sure you have the :ref:`selenium dependencies
<selenium_dependencies>` installed locally first):

.. code-block:: shell

    ./runtests

Run quality assurance tests with:

.. code-block:: shell

    ./run-qa-checks

Alternative Sources
-------------------

Pypi
~~~~

To install the latest Pypi:

.. code-block:: shell

    pip install openwisp-controller

Github
~~~~~~

To install the latest development version tarball via HTTPs:

.. code-block:: shell

    pip install https://github.com/openwisp/openwisp-controller/tarball/master

Alternatively you can use the git protocol:

.. code-block:: shell

    pip install -e git+git://github.com/openwisp/openwisp-controller#egg=openwisp_controller

.. _vagrant_troubleshooting:

Vagrant and VirtualBox Troubleshooting (FAQ)
--------------------------------------------

.. important::

    These issues are common when running the OpenWISP development VM using Vagrant + VirtualBox.

If you encounter issues when running Vagrant, please check these common solutions:

VT-x / AMD-V Virtualization Technology is Disabled
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** ``vagrant up`` fails with errors mentioning that **VT-x (Intel)** or **AMD-V** is required but disabled.

**Solution:**

* **Enable Virtualization in BIOS:** You must reboot your computer and enter your **BIOS/UEFI settings** to manually enable the virtualization feature (usually found under CPU or Security settings).
* **Check Conflicts:** Ensure that other hypervisors (like **VMware**) are disabled or uninstalled. **Windows Users:** Check and disable **Hyper-V** via: Control Panel → Programs → Turn Windows features on/off.

Driver Mismatch Error (VERR_VM_DRIVER_VERSION_MISMATCH)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** A ``VERR_VM_DRIVER_VERSION_MISMATCH (-1912)`` error appears, often after a recent kernel update on Linux.

**Solution:** This means the VirtualBox kernel modules no longer match your running kernel.
* **Debian/Ubuntu:** Try reconfiguring the kernel modules:

    .. code-block:: shell

        sudo dpkg-reconfigure virtualbox-dkms

* **Other Linux:** Consult your distribution's documentation for rebuilding or reinstalling VirtualBox kernel drivers.

Nested Virtualization Failure (Including WSL2)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** ``vagrant up`` fails when run inside another Virtual Machine (VM) or inside **WSL2**.

**Solution:** VirtualBox/Vagrant generally **cannot run inside another VM or inside WSL2**.
* **WSL2 Note:** You must run the Vagrant commands in **Windows PowerShell** or **Git Bash** on your host Windows machine, not within the WSL2 terminal.
* **General:** Run the commands directly on your **Host Operating System** (the main OS running on your physical hardware).

Shared Folder Sync Failure
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** Local changes to the source code are not appearing inside the Vagrant VM, or vice versa.

**Solution:** This is usually an issue with VirtualBox Guest Additions or Windows conflicts.
* **Rebuild:** If the issue persists, destroy and rebuild the VM to ensure the latest Guest Additions are installed:

    .. code-block:: shell

        vagrant destroy
        vagrant up

* **Windows/Hyper-V:** Ensure Hyper-V is completely disabled, as it commonly interferes with VirtualBox's file system drivers.

Installation on Non-Ubuntu Linux Distributions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** Issues installing VirtualBox or Vagrant on non-Debian/Ubuntu systems (e.g., Arch, Fedora, Manjaro).

**Solution:** The best documentation for driver and package installation is provided by your specific distribution.
* **General Advice:** Consult your distribution's official wiki or package manager guide (e.g., the `Manjaro Wiki for VirtualBox <https://wiki.manjaro.org/index.php?title=VirtualBox>`_).


If these steps don't solve your issue, please open a discussion on GitHub with your host OS details for further assistance.

.. _controller_dev_docker:

Install and Run on Docker
-------------------------

.. warning::

    This Docker image is for development purposes only.

    For the official OpenWISP Docker images, see: :doc:`docker-openwisp
    </docker/index>`.

Build from the Dockerfile:

.. code-block:: shell

    docker compose build

Run the docker container:

.. code-block:: shell

    docker compose up

Troubleshooting Steps for Common Installation Issues
----------------------------------------------------

You may encounter some issues while installing GeoDjango.

Unable to Load SpatiaLite library Extension?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are incurring in the following exception:

.. code-block::

    django.core.exceptions.ImproperlyConfigured: Unable to load the SpatiaLite library extension

You need to specify ``SPATIALITE_LIBRARY_PATH`` in your ``settings.py`` as
explained in `django documentation regarding how to install and configure
spatialte
<https://docs.djangoproject.com/en/4.2/ref/contrib/gis/install/spatialite/>`_.

Having Issues with Other Geospatial Libraries?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Please refer `troubleshooting issues related to geospatial libraries
<https://docs.djangoproject.com/en/4.2/ref/contrib/gis/install/#library-environment-settings/>`_.

.. important::

    If you want to add OpenWISP Controller to an existing Django project,
    then you can refer to the `test project in the openwisp-controller
    repository
    <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2>`_.
