openwisp-controller
===================

.. image:: https://travis-ci.org/openwisp/openwisp-controller.svg
   :target: https://travis-ci.org/openwisp/openwisp-controller

.. image:: https://coveralls.io/repos/openwisp/openwisp-controller/badge.svg
  :target: https://coveralls.io/r/openwisp/openwisp-controller

.. image:: https://requires.io/github/openwisp/openwisp-controller/requirements.svg?branch=master
   :target: https://requires.io/github/openwisp/openwisp-controller/requirements/?branch=master
   :alt: Requirements Status

.. image:: https://badge.fury.io/py/openwisp-controller.svg
   :target: http://badge.fury.io/py/openwisp-controller

------------

OpenWISP 2 controller module (built using Python and the Django web-framework).

**Want to help OpenWISP?** `Find out how to help us grow here
<http://openwisp.io/docs/general/help-us.html>`_.

------------

.. contents:: **Table of Contents**:
   :backlinks: none
   :depth: 3

------------

Deploy it in production
-----------------------

An automated installer is available at `ansible-openwisp2 <https://github.com/openwisp/ansible-openwisp2>`_.

Dependencies
------------

* Python >= 3.6
* OpenSSL

Install stable version from pypi
--------------------------------

Install from pypi:

.. code-block:: shell

    pip install openwisp-controller

Install development version
---------------------------

Install tarball:

.. code-block:: shell

    pip install https://github.com/openwisp/openwisp-controller/tarball/master

Alternatively you can install via pip using git:

.. code-block:: shell

    pip install -e git+git://github.com/openwisp/openwisp-controller#egg=openwisp_controller

If you want to contribute, follow the instructions in
`Installing for development <#installing-for-development>`_.

Setup (integrate in an existing django project)
-----------------------------------------------

``INSTALLED_APPS`` and ``EXTENDED_APPS`` (an internal openwisp2 setting) in ``settings.py``
should look like the following (ordering is important):

.. code-block:: python

    INSTALLED_APPS = [
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'django.contrib.gis',
        # openwisp2 admin theme
        # (must be loaded here)
        'openwisp_utils.admin_theme',
        # all-auth
        'django.contrib.sites',
        'allauth',
        'allauth.account',
        'allauth.socialaccount',
        'django_extensions',
        # openwisp2 module
        'openwisp_controller.config',
        'openwisp_controller.pki',
        'openwisp_controller.geo',
        'openwisp_controller.connection',
        'openwisp_users',
        # admin
        'django.contrib.admin',
        # other dependencies
        'sortedm2m',
        'reversion',
        'leaflet',
        # rest framework
        'rest_framework',
        'rest_framework_gis',
        # channels
        'channels',
    ]

    EXTENDED_APPS = ('django_netjsonconfig', 'django_x509', 'django_loci',)

Ensure you are using one of the available geodjango backends, eg:

.. code-block:: python

    DATABASES = {
        'default': {
            'ENGINE': 'django.contrib.gis.db.backends.spatialite',
            'NAME': 'openwisp-controller.db',
        }
    }

Add ``openwisp_utils.staticfiles.DependencyFinder`` to ``STATICFILES_FINDERS`` in your ``settings.py``:

.. code-block:: python

    STATICFILES_FINDERS = [
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
        'openwisp_utils.staticfiles.DependencyFinder',
    ]

Add ``openwisp_utils.loaders.DependencyLoader`` to template loaders
and ``openwisp_utils.admin_theme.context_processor.menu_items`` to
context processors in the ``TEMPLATES`` setting of ``settings.py``:

.. code-block:: python

    TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                    'openwisp_utils.loaders.DependencyLoader',
                ],
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                    'openwisp_utils.admin_theme.context_processor.menu_items'
                ],
            },
        }
    ]

Add the following settings to ``settings.py``:

.. code-block:: python

    FORM_RENDERER = 'django.forms.renderers.TemplatesSetting'

    ASGI_APPLICATION = 'openwisp_controller.geo.channels.routing.channel_routing'
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer'
        },
    }

    LOGIN_REDIRECT_URL = 'admin:index'
    ACCOUNT_LOGOUT_REDIRECT_URL = LOGIN_REDIRECT_URL

``urls.py``:

.. code-block:: python

    from django.conf import settings
    from django.conf.urls import include, url
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    from openwisp_utils.admin_theme.admin import admin, openwisp_admin

    openwisp_admin()

    urlpatterns = [
        url(r'^admin/', include(admin.site.urls)),
        url(r'', include('openwisp_controller.urls')),
    ]

    urlpatterns += staticfiles_urlpatterns()

Settings
--------

``OPENWISP_CONNECTORS``
~~~~~~~~~~~~~~~~~~~~~~~

+--------------+--------------------------------------------------------------------+
| **type**:    | ``tuple``                                                          |
+--------------+--------------------------------------------------------------------+
| **default**: | .. code-block:: python                                             |
|              |                                                                    |
|              |   (                                                                |
|              |     ('openwisp_controller.connection.connectors.ssh.Ssh', 'SSH'),  |
|              |   )                                                                |
+--------------+--------------------------------------------------------------------+

Available connector classes. Connectors are python classes that specify ways
in which OpenWISP can connect to devices in order to launch commands.

``OPENWISP_UPDATE_STRATEGIES``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+----------------------------------------------------------------------------------------+
| **type**:    | ``tuple``                                                                              |
+--------------+----------------------------------------------------------------------------------------+
| **default**: | .. code-block:: python                                                                 |
|              |                                                                                        |
|              |   (                                                                                    |
|              |     ('openwisp_controller.connection.connectors.openwrt.ssh.OpenWrt', 'OpenWRT SSH'),  |
|              |   )                                                                                    |
+--------------+----------------------------------------------------------------------------------------+

Available update strategies. An update strategy is a subclass of a
connector class which defines an ``update_config`` method which is
in charge of updating the configuratio of the device.

This operation is launched in a background worker when the configuration
of a device is changed.

It's possible to write custom update strategies and add them to this
setting to make them available in OpenWISP.

``OPENWISP_CONFIG_UPDATE_MAPPING``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+--------------------------------------------------------------------+
| **type**:    | ``dict``                                                           |
+--------------+--------------------------------------------------------------------+
| **default**: | .. code-block:: python                                             |
|              |                                                                    |
|              |   {                                                                |
|              |     'netjsonconfig.OpenWrt': OPENWISP_UPDATE_STRATEGIES[0][0],     |
|              |   }                                                                |
+--------------+--------------------------------------------------------------------+

A dictionary that maps configuration backends to update strategies in order to
automatically determine the update strategy of a device connection if the
update strategy field is left blank by the user.

Installing for development
--------------------------

Install the dependencies:

.. code-block:: shell

    sudo apt -y install sqlite3 libsqlite3-dev openssl libssl-dev
    sudo apt -y install gdal-bin libproj-dev libgeos-dev libspatialite-dev libsqlite3-mod-spatialite
    sudo apt -y install redis

Install your forked repo with `pipenv <https://pipenv.readthedocs.io/en/latest/>`_:

.. code-block:: shell

    git clone git://github.com/<your_fork>/openwisp-controller
    cd openwisp-controller/
    pipenv install --three --dev --skip-lock  # skip-lock is faster (optional)
    pipenv run install_dev

Create database:

.. code-block:: shell

    cd tests/
    pipenv run ./manage.py migrate
    pipenv run ./manage.py createsuperuser

Launch celery worker (for background jobs):

.. code-block:: shell

    celery -A openwisp2 worker -l info

Launch development server:

.. code-block:: shell

    pipenv run ./manage.py runserver 0.0.0.0:8000

You can access the admin interface at http://127.0.0.1:8000/admin/.

Run tests with:

.. code-block:: shell

    pipenv run test

Install and run on docker
--------------------------

Build from the Dockerfile:

.. code-block:: shell

    docker-compose build

Run the docker container:

.. code-block:: shell

    docker-compose up

Troubleshooting Steps
---------------------

You may encounter some issues while installing GeoDjango.

Unable to load SpatiaLite library extension?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are getting below exception::

   django.core.exceptions.ImproperlyConfigured: Unable to load the SpatiaLite library extension

then, You need to specify ``SPATIALITE_LIBRARY_PATH`` in your ``settings.py`` as explained in
`django documentation regarding how to install and configure spatialte
<https://docs.djangoproject.com/en/2.1/ref/contrib/gis/install/spatialite/>`_.

Having Issues with other geospatial libraries?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Please refer
`troubleshooting issues related to geospatial libraries
<https://docs.djangoproject.com/en/2.1/ref/contrib/gis/install/#library-environment-settings/>`_.

Talks
-----

- `OpenWISP2 - a self hosted solution to control OpenWRT/LEDE devices
  <https://fosdem.org/2017/schedule/event/openwisp2/>`_ (FOSDEM 2017)

Contributing
------------

Please read the `OpenWISP contributing guidelines
<http://openwisp.io/docs/developer/contributing.html>`_
and also keep in mind the following:

1. Announce your intentions in the `OpenWISP Mailing List <https://groups.google.com/d/forum/openwisp>`_
2. Fork this repo and install it
3. Follow `PEP8, Style Guide for Python Code`_
4. Write code
5. Write tests for your code
6. Ensure all tests pass
7. Ensure test coverage does not decrease
8. Document your changes
9. Send pull request

.. _PEP8, Style Guide for Python Code: http://www.python.org/dev/peps/pep-0008/

Changelog
---------

See `CHANGES <https://github.com/openwisp/openwisp-controller/blob/master/CHANGES.rst>`_.

License
-------

See `LICENSE <https://github.com/openwisp/openwisp-controller/blob/master/LICENSE>`_.
