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

* Python 2.7 or Python >= 3.4
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

If you want to contribute, install your cloned fork:

.. code-block:: shell

    git clone git@github.com:<your_fork>/openwisp-controller.git
    cd openwisp_controller
    python setup.py develop

Setup (integrate in an existing django project)
-----------------------------------------------

``INSTALLED_APPS`` in ``settings.py`` should look like the following (ordering is important):

.. code-block:: python

    INSTALLED_APPS = [
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        # all-auth
        'django.contrib.sites',
        'allauth',
        'allauth.account',
        'allauth.socialaccount',
        'django_extensions',
        # openwisp2 modules
        'openwisp_users',
        'openwisp_controller.pki',
        'openwisp_controller.config',
        # admin
        'django_netjsonconfig.admin_theme',
        'django.contrib.admin',
        # other dependencies
        'sortedm2m',
        'reversion',
    ]

Add ``openwisp_controller.staticfiles.DependencyFinder`` to ``STATICFILES_FINDERS`` in your ``settings.py``

.. code-block:: python

    STATICFILES_FINDERS = [
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
        'openwisp_controller.staticfiles.DependencyFinder',
    ]

Add ``openwisp_controller.loaders.DependencyLoader`` to ``TEMPLATES`` in your ``settings.py``

.. code-block:: python

    TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'OPTIONS': {
                'loaders': [
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                    # add the following line
                    'openwisp_controller.loaders.DependencyLoader'
                ],
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                ],
            },
        }
    ]

Add the following settings to ``settings.py``:

.. code-block:: python

    LOGIN_REDIRECT_URL = 'admin:index'
    ACCOUNT_LOGOUT_REDIRECT_URL = LOGIN_REDIRECT_URL

``urls.py``:

.. code-block:: python

    from django.conf import settings
    from django.conf.urls import include, url
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    from django_netjsonconfig.admin_theme.admin import admin, openwisp_admin

    openwisp_admin()

    urlpatterns = [
        url(r'^admin/', include(admin.site.urls)),
        url(r'', include('openwisp_controller.urls')),
    ]

    urlpatterns += staticfiles_urlpatterns()

Talks
-----

- `OpenWISP2 - a self hosted solution to control OpenWRT/LEDE devices
  <https://fosdem.org/2017/schedule/event/openwisp2/>`_ (FOSDEM 2017)

Contributing
------------

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
