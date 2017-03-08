openwisp-controller
===================

.. image:: https://travis-ci.org/openwisp/openwisp-controller.svg
   :target: https://travis-ci.org/openwisp/openwisp-controller

.. image:: https://coveralls.io/repos/openwisp/openwisp-controller/badge.svg
  :target: https://coveralls.io/r/openwisp/openwisp-controller

.. image:: https://requires.io/github/openwisp/openwisp-controller/requirements.svg?branch=master
   :target: https://requires.io/github/openwisp/openwisp-controller/requirements/?branch=master
   :alt: Requirements Status

.. image:: https://badge.fury.io/py/openwisp_controller.svg
   :target: http://badge.fury.io/py/openwisp_controller

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

TODO

Project goals
-------------

TODO

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

TODO

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


.. code-block:: python


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

Changelog
---------

See `CHANGES <https://github.com/openwisp/openwisp-controller/blob/master/CHANGES.rst>`_.

License
-------

See `LICENSE <https://github.com/openwisp/openwisp-controller/blob/master/LICENSE>`_.
