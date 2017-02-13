openwisp2
=========

.. image:: https://travis-ci.org/nemesisdesign/openwisp2.svg
   :target: https://travis-ci.org/nemesisdesign/openwisp2

.. image:: https://coveralls.io/repos/nemesisdesign/openwisp2/badge.svg
  :target: https://coveralls.io/r/nemesisdesign/openwisp2

.. image:: https://requires.io/github/nemesisdesign/openwisp2/requirements.svg?branch=master
   :target: https://requires.io/github/nemesisdesign/openwisp2/requirements/?branch=master
   :alt: Requirements Status

.. image:: https://badge.fury.io/py/openwisp2.svg
   :target: http://badge.fury.io/py/openwisp2

------------

OpenWISP2 prototype. Work in progress. Do not use in production.

OpenWISP2 is a simple web app composed of several reusable python libraries and django apps. Having learnt from the experience with OpenWISP1, the new version of the controller has been redesigned to be more flexible, reusable, modularly built and easier to deploy.

Its goal is to make it easier to maintain a network of devices based on OpenWRT/LEDE.

------------

.. contents:: **Table of Contents**:
   :backlinks: none
   :depth: 3

------------

Current features
----------------

- Configuration management for embedded devices supporting different firmwares: OpenWRT/LEDE and OpenWISP Firmware
- Support for additional firmware can be added by specifying custom backends
- Configuration editor based on JSON-Schema editor
- Advanced edit mode: edit NetJSON DeviceConfiguration objects for maximum flexibility
- Configuration templates: reduce repetition to the minimum
- Configuration context: reference ansible-like variables in the configuration
- Simple HTTP resources: allow devices to automatically download configuration updates
- VPN management: easily create VPN servers and clients

Project goals
-------------

- Automate configuration management for embedded devices
- Allow to minimize repetition by using templates
- Make it easy to integrate in larger django projects to improve reusability
- Make it easy to extend its models by providing abstract models
- Provide ways to support more firmwares by adding custom backends
- Keep the core as simple as possible
- Provide ways to extend the default behaviour
- Encourage new features to be published as extensions

Dependencies
------------

* Python 2.7 or Python >= 3.4
* OpenSSL

Install stable version from pypi
--------------------------------

Install from pypi:

.. code-block:: shell

    pip install openwisp2

Install development version
---------------------------

Install tarball:

.. code-block:: shell

    pip install https://github.com/openwisp/openwisp2/tarball/master

Alternatively you can install via pip using git:

.. code-block:: shell

    pip install -e git+git://github.com/openwisp/openwisp2#egg=openwisp2

If you want to contribute, install your cloned fork:

.. code-block:: shell

    git clone git@github.com:<your_fork>/openwisp2.git
    cd openwisp2
    python setup.py develop

Setup (integrate in an existing django project)
-----------------------------------------------

TODO

Add ``openwisp2.staticfiles.DependencyFinder`` to ``STATICFILES_FINDERS`` in your ``settings.py``

.. code-block:: python

    STATICFILES_FINDERS = [
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
        'openwisp2.staticfiles.DependencyFinder',
    ]

Add ``openwisp2.loaders.DependencyLoader`` to ``TEMPLATES`` in your ``settings.py``

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
                    'openwisp2.loaders.DependencyLoader'
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

Add ``allauth.account.auth_backends.AuthenticationBackend`` to ``AUTHENTICATION_BACKENDS`` in your ``settings.py``

.. code-block:: python

    AUTHENTICATION_BACKENDS = (
        'django.contrib.auth.backends.ModelBackend',
        'allauth.account.auth_backends.AuthenticationBackend',
    )

Deploy it in production
-----------------------

TODO

Installing for development
--------------------------

TODO

Settings
--------

TODO

Screenshots
-----------

TODO

Talks
-----

- `OpenWISP2 - a self hosted solution to control OpenWRT/LEDE devices <https://fosdem.org/2017/schedule/event/openwisp2/>`_ (FOSDEM 2017)

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
.. _NetJSON: http://netjson.org
.. _netjsonconfig: http://netjsonconfig.openwisp.org

Changelog
---------

See `CHANGES <https://github.com/openwisp/openwisp2/blob/master/CHANGES.rst>`_.

License
-------

See `LICENSE <https://github.com/openwisp/openwisp2/blob/master/LICENSE>`_.
