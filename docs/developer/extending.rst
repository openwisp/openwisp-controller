Extending OpenWISP Controller
=============================

.. include:: ../partials/developer-docs.rst

One of the core values of the OpenWISP project is :ref:`Software
Reusability <values_software_reusability>`, for this reason *OpenWISP
Controller* provides a set of base classes which can be imported, extended
and reused to create derivative apps.

In order to implement your custom version of *OpenWISP Controller*, you
need to perform the steps described in this section.

When in doubt, the code in the `test project
<https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/>`_
will serve you as source of truth: just replicate and adapt that code to
get a basic derivative of *OpenWISP Controller* working.

If you want to add new users fields, please follow the :doc:`tutorial to
extend the openwisp-users module </users/developer/extending>`. As an
example, we have extended *openwisp-users* to *sample_users* app and added
a field ``social_security_number`` in the `sample_users/models.py
<https://github.com/openwisp/openwisp-controller/blob/master/tests/openwisp2/sample_users/models.py>`_.

.. important::

    If you plan on using a customized version of this module, we suggest
    to start with it since the beginning, because migrating your data from
    the default module to your extended version may be time consuming.

.. contents:: **Table of Contents**:
    :depth: 2
    :local:

1. Initialize Your Project & Custom Apps
----------------------------------------

Firstly, to get started you need to create a django project:

.. code-block:: bash

    django-admin startproject mycontroller

Now, you need to do is to create some new django apps which will contain
your custom version of *OpenWISP Controller*.

A django project is a collection of django apps. There are 4 django apps
in the openwisp_controller project, namely *config*, *pki*, *connection* &
*geo*. You'll need to create 4 apps in your project for each app in
*openwisp-controller*.

A django app is nothing more than a `python package
<https://docs.python.org/3/tutorial/modules.html#packages>`_ (a directory
of python scripts), in the following examples we'll call these django app
``sample_config``, ``sample_pki``, ``sample_connection``, ``sample_geo`` &
``sample_subnet_division``. but you can name it how you want:

.. code-block:: bash

    django-admin startapp sample_config
    django-admin startapp sample_pki
    django-admin startapp sample_connection
    django-admin startapp sample_geo
    django-admin startapp sample_subnet_division

Keep in mind that the command mentioned above must be called from a
directory which is available in your `PYTHON_PATH
<https://docs.python.org/3/using/cmdline.html#envvar-PYTHONPATH>`_ so that
you can then import the result into your project.

For more information about how to work with django projects and django
apps, please refer to the `django documentation
<https://docs.djangoproject.com/en/4.2/intro/tutorial01/>`_.

2. Install ``openwisp-controller``
----------------------------------

Install (and add to the requirement of your project) openwisp-controller:

.. code-block:: bash

    pip install openwisp-controller

3. Add Your Apps to ``INSTALLED_APPS``
--------------------------------------

Now you need to add ``mycontroller.sample_config``,
``mycontroller.sample_pki``, ``mycontroller.sample_connection``,
``mycontroller.sample_geo`` & ``mycontroller.sample_subnet_division`` to
``INSTALLED_APPS`` in your ``settings.py``, ensuring also that
``openwisp_controller.config``, ``openwisp_controller.geo``,
``openwisp_controller.pki``, ``openwisp_controller.connnection`` &
``openwisp_controller.subnet_division`` have been removed:

.. code-block:: python

    # Remember: Order in INSTALLED_APPS is important.
    INSTALLED_APPS = [
        # other django installed apps
        "openwisp_utils.admin_theme",
        "admin_auto_filters",
        # all-auth
        "django.contrib.sites",
        "allauth",
        "allauth.account",
        "allauth.socialaccount",
        # openwisp2 module
        # 'openwisp_controller.config', <-- comment out or delete this line
        # 'openwisp_controller.pki', <-- comment out or delete this line
        # 'openwisp_controller.geo', <-- comment out or delete this line
        # 'openwisp_controller.connection', <-- comment out or delete this line
        # 'openwisp_controller.subnet_division', <-- comment out or delete this line
        "mycontroller.sample_config",
        "mycontroller.sample_pki",
        "mycontroller.sample_geo",
        "mycontroller.sample_connection",
        "mycontroller.sample_subnet_division",
        "openwisp_users",
        # admin
        "django.contrib.admin",
        # other dependencies
        "sortedm2m",
        "reversion",
        "leaflet",
        # rest framework
        "rest_framework",
        "rest_framework_gis",
        # channels
        "channels",
        # django-import-export
        "import_export",
    ]

Substitute ``mycontroller``, ``sample_config``, ``sample_pki``,
``sample_connection``, ``sample_geo`` & ``sample_subnet_division`` with
the name you chose in step 1.

4. Add ``EXTENDED_APPS``
------------------------

Add the following to your ``settings.py``:

.. code-block:: python

    EXTENDED_APPS = (
        "django_x509",
        "django_loci",
        "openwisp_controller.config",
        "openwisp_controller.pki",
        "openwisp_controller.geo",
        "openwisp_controller.connection",
        "openwisp_controller.subnet_division",
    )

5. Add ``openwisp_utils.staticfiles.DependencyFinder``
------------------------------------------------------

Add ``openwisp_utils.staticfiles.DependencyFinder`` to
``STATICFILES_FINDERS`` in your ``settings.py``:

.. code-block:: python

    STATICFILES_FINDERS = [
        "django.contrib.staticfiles.finders.FileSystemFinder",
        "django.contrib.staticfiles.finders.AppDirectoriesFinder",
        "openwisp_utils.staticfiles.DependencyFinder",
    ]

6. Add ``openwisp_utils.loaders.DependencyLoader``
--------------------------------------------------

Add ``openwisp_utils.loaders.DependencyLoader`` to ``TEMPLATES`` in your
``settings.py``, but ensure it comes before
``django.template.loaders.app_directories.Loader``:

.. code-block:: python

    TEMPLATES = [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "OPTIONS": {
                "loaders": [
                    "django.template.loaders.filesystem.Loader",
                    "openwisp_utils.loaders.DependencyLoader",
                    "django.template.loaders.app_directories.Loader",
                ],
                "context_processors": [
                    "django.template.context_processors.debug",
                    "django.template.context_processors.request",
                    "django.contrib.auth.context_processors.auth",
                    "django.contrib.messages.context_processors.messages",
                    "openwisp_utils.admin_theme.context_processor.menu_items",
                    "openwisp_notifications.context_processors.notification_api_settings",
                ],
            },
        }
    ]

7. Initial Database Setup
-------------------------

Ensure you are using one of the available geodjango backends, e.g.:

.. code-block:: python

    DATABASES = {
        "default": {
            "ENGINE": "openwisp_utils.db.backends.spatialite",
            "NAME": "openwisp-controller.db",
        }
    }

For more information about GeoDjango, please refer to the `geodjango
documentation <https://docs.djangoproject.com/en/4.2/ref/contrib/gis/>`_.

8. Django Channels Setup
------------------------

Create ``asgi.py`` in your project folder and add following lines in it:

.. code-block:: python

    from channels.auth import AuthMiddlewareStack
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.security.websocket import AllowedHostsOriginValidator
    from django.core.asgi import get_asgi_application

    from openwisp_controller.routing import get_routes

    # You can also add your routes like this
    from my_app.routing import my_routes

    application = ProtocolTypeRouter(
        {
            "http": get_asgi_application(),
            "websocket": AllowedHostsOriginValidator(
                AuthMiddlewareStack(URLRouter(get_routes() + my_routes))
            ),
        }
    )

9. Other Settings
-----------------

Add the following settings to ``settings.py``:

.. code-block:: python

    FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

    ASGI_APPLICATION = "my_project.asgi.application"
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    }

For more information about FORM_RENDERER setting, please refer to the
`FORM_RENDERER documentation
<https://docs.djangoproject.com/en/4.2/ref/settings/#form-renderer>`_. For
more information about ASGI_APPLICATION setting, please refer to the
`ASGI_APPLICATION documentation
<https://channels.readthedocs.io/en/latest/deploying.html#configuring-the-asgi-application>`_.
For more information about CHANNEL_LAYERS setting, please refer to the
`CHANNEL_LAYERS documentation
<https://channels.readthedocs.io/en/latest/deploying.html#setting-up-a-channel-backend>`_.

10. Inherit the AppConfig Class
-------------------------------

Please refer to the following files in the sample app of the test project:

- ``sample_config``:
      - `sample_config/__init__.py
        <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/__init__.py>`_.
      - `sample_config/apps.py
        <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/apps.py>`_.
- ``sample_geo``:
      - `sample_geo/__init__.py
        <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/__init__.py>`_.
      - `sample_geo/apps.py
        <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/apps.py>`_.
- ``sample_pki``:
      - `sample_pki/__init__.py
        <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_pki/__init__.py>`_.
      - `sample_pki/apps.py
        <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_pki/apps.py>`_.
- ``sample_connection``:
      - `sample_connection/__init__.py
        <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_connection/__init__.py>`_.
      - `sample_connection/apps.py
        <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_connection/apps.py>`_.
- ``sample_subnet_division``:
      - `sample_subnet_division/__init__.py
        <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_subnet_division/__init__.py>`_.
      - `sample_subnet_division/apps.py
        <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_subnet_division/apps.py>`_.

You have to replicate and adapt that code in your project.

For more information regarding the concept of ``AppConfig`` please refer
to the `"Applications" section in the django documentation
<https://docs.djangoproject.com/en/4.2/ref/applications/>`_.

11. Create Your Custom Models
-----------------------------

For the purpose of showing an example, we added a simple "details" field
to the models of the sample app in the test project.

- `sample_config models
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/models.py>`_
- `sample_geo models
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/models.py>`_
- `sample_pki models
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_pki/models.py>`_
- `sample_connection models
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_connection/models.py>`_
- `sample_subnet_division
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_subnet_division/models.py>`_

You can add fields in a similar way in your ``models.py`` file.

.. note::

    If you have any doubt regarding how to use, extend or develop models
    please refer to the `"Models" section in the django documentation
    <https://docs.djangoproject.com/en/4.2/topics/db/models/>`_.

12. Add Swapper Configurations
------------------------------

Once you have created the models, add the following to your
``settings.py``:

.. code-block:: python

    # Setting models for swapper module
    CONFIG_DEVICE_MODEL = "sample_config.Device"
    CONFIG_DEVICEGROUP_MODEL = "sample_config.DeviceGroup"
    CONFIG_CONFIG_MODEL = "sample_config.Config"
    CONFIG_TEMPLATETAG_MODEL = "sample_config.TemplateTag"
    CONFIG_TAGGEDTEMPLATE_MODEL = "sample_config.TaggedTemplate"
    CONFIG_TEMPLATE_MODEL = "sample_config.Template"
    CONFIG_VPN_MODEL = "sample_config.Vpn"
    CONFIG_VPNCLIENT_MODEL = "sample_config.VpnClient"
    CONFIG_ORGANIZATIONCONFIGSETTINGS_MODEL = "sample_config.OrganizationConfigSettings"
    CONFIG_ORGANIZATIONLIMITS_MODEL = "sample_config.OrganizationLimits"
    CONFIG_WHOISINFO_MODEL = "sample_config.WHOISInfo"
    DJANGO_X509_CA_MODEL = "sample_pki.Ca"
    DJANGO_X509_CERT_MODEL = "sample_pki.Cert"
    GEO_LOCATION_MODEL = "sample_geo.Location"
    GEO_FLOORPLAN_MODEL = "sample_geo.FloorPlan"
    GEO_DEVICELOCATION_MODEL = "sample_geo.DeviceLocation"
    CONNECTION_CREDENTIALS_MODEL = "sample_connection.Credentials"
    CONNECTION_DEVICECONNECTION_MODEL = "sample_connection.DeviceConnection"
    CONNECTION_COMMAND_MODEL = "sample_connection.Command"
    SUBNET_DIVISION_SUBNETDIVISIONRULE_MODEL = "sample_subnet_division.SubnetDivisionRule"
    SUBNET_DIVISION_SUBNETDIVISIONINDEX_MODEL = "sample_subnet_division.SubnetDivisionIndex"

Substitute ``sample_config``, ``sample_pki``, ``sample_connection``,
``sample_geo`` & ``sample_subnet_division`` with the name you chose in
step 1.

13. Create Database Migrations
------------------------------

Create database migrations:

.. code-block:: bash

    ./manage.py makemigrations

Now, to use the default ``administrator`` and ``operator`` user groups
like the used in the openwisp_controller module, you'll manually need to
make a migrations file which would look like:

- `sample_config/migrations/0002_default_groups_permissions.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/migrations/0002_default_groups_permissions.py>`_
- `sample_geo/migrations/0002_default_group_permissions.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/migrations/0002_default_group_permissions.py>`_
- `sample_pki/migrations/0002_default_group_permissions.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_pki/migrations/0002_default_group_permissions.py>`_
- `sample_connection/migrations/0002_default_group_permissions.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_connection/migrations/0002_default_group_permissions.py>`_
- `sample_subnet_division/migrations/0002_default_group_permissions.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_subnet_division/migrations/0002_default_group_permissions.py>`_

Create database migrations:

.. code-block:: bash

    ./manage.py migrate

For more information, refer to the `"Migrations" section in the django
documentation
<https://docs.djangoproject.com/en/4.2/topics/migrations/>`_.

14. Create the Admin
--------------------

Refer to the ``admin.py`` file of the sample app.

- `sample_config admin.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/admin.py>`_.
- `sample_geo admin.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/admin.py>`_.
- `sample_pki admin.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_pki/admin.py>`_.
- `sample_connection admin.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_connection/admin.py>`_.
- `sample_subnet_division admin.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_subnet_division/admin.py>`_.

To introduce changes to the admin, you can do it in two main ways which
are described below.

.. note::

    For more information regarding how the django admin works, or how it
    can be customized, please refer to `"The django admin site" section in
    the django documentation
    <https://docs.djangoproject.com/en/4.2/ref/contrib/admin/>`_.

14.1. Monkey Patching
~~~~~~~~~~~~~~~~~~~~~

If the changes you need to add are relatively small, you can resort to
monkey patching.

For example:

``sample_config``
+++++++++++++++++

.. code-block:: python

    from openwisp_controller.config.admin import (
        DeviceAdmin,
        DeviceGroupAdmin,
        TemplateAdmin,
        VpnAdmin,
    )

    DeviceAdmin.fields += ["example"]  # <-- monkey patching example

``sample_connection``
+++++++++++++++++++++

.. code-block:: python

    from openwisp_controller.connection.admin import CredentialsAdmin

    CredentialsAdmin.fields += ["example"]  # <-- monkey patching example

``sample_geo``
++++++++++++++

.. code-block:: python

    from openwisp_controller.geo.admin import FloorPlanAdmin, LocationAdmin

    FloorPlanAdmin.fields += ["example"]  # <-- monkey patching example

``sample_pki``
++++++++++++++

.. code-block:: python

    from openwisp_controller.pki.admin import CaAdmin, CertAdmin

    CaAdmin.fields += ["example"]  # <-- monkey patching example

``sample_subnet_division``
++++++++++++++++++++++++++

.. code-block:: python

    from openwisp_controller.subnet_division.admin import (
        SubnetDivisionRuleInlineAdmin,
    )

    SubnetDivisionRuleInlineAdmin.fields += ["example"]  # <-- monkey patching example

14.2. Inheriting admin classes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you need to introduce significant changes and/or you don't want to
resort to monkey patching, you can proceed as follows:

``sample_config``
+++++++++++++++++

.. code-block:: python

    from django.contrib import admin
    from openwisp_controller.config.admin import (
        DeviceAdmin as BaseDeviceAdmin,
        TemplateAdmin as BaseTemplateAdmin,
        VpnAdmin as BaseVpnAdmin,
        DeviceGroupAdmin as BaseDeviceGroupAdmin,
    )
    from swapper import load_model

    Vpn = load_model("openwisp_controller", "Vpn")
    Device = load_model("openwisp_controller", "Device")
    DeviceGroup = load_model("openwisp_controller", "DeviceGroup")
    Template = load_model("openwisp_controller", "Template")

    admin.site.unregister(Vpn)
    admin.site.unregister(Device)
    admin.site.unregister(DeviceGroup)
    admin.site.unregister(Template)


    @admin.register(Vpn)
    class VpnAdmin(BaseVpnAdmin):
        # add your changes here
        pass


    @admin.register(Device)
    class DeviceAdmin(BaseDeviceAdmin):
        # add your changes here
        pass


    @admin.register(DeviceGroup)
    class DeviceGroupAdmin(BaseDeviceGroupAdmin):
        # add your changes here
        pass


    @admin.register(Template)
    class TemplateAdmin(BaseTemplateAdmin):
        # add your changes here
        pass

``sample_connection``
+++++++++++++++++++++

.. code-block:: python

    from openwisp_controller.connection.admin import (
        CredentialsAdmin as BaseCredentialsAdmin,
    )
    from django.contrib import admin
    from swapper import load_model

    Credentials = load_model("openwisp_controller", "Credentials")

    admin.site.unregister(Credentials)


    @admin.register(Device)
    class CredentialsAdmin(BaseCredentialsAdmin):
        pass
        # add your changes here

``sample_geo``
++++++++++++++

.. code-block:: python

    from openwisp_controller.geo.admin import (
        FloorPlanAdmin as BaseFloorPlanAdmin,
        LocationAdmin as BaseLocationAdmin,
    )
    from django.contrib import admin
    from swapper import load_model

    Location = load_model("openwisp_controller", "Location")
    FloorPlan = load_model("openwisp_controller", "FloorPlan")

    admin.site.unregister(FloorPlan)
    admin.site.unregister(Location)


    @admin.register(FloorPlan)
    class FloorPlanAdmin(BaseFloorPlanAdmin):
        pass
        # add your changes here


    @admin.register(Location)
    class LocationAdmin(BaseLocationAdmin):
        pass
        # add your changes here

``sample_pki``
++++++++++++++

.. code-block:: python

    from openwisp_controller.geo.admin import (
        CaAdmin as BaseCaAdmin,
        CertAdmin as BaseCertAdmin,
    )
    from django.contrib import admin
    from swapper import load_model

    Ca = load_model("openwisp_controller", "Ca")
    Cert = load_model("openwisp_controller", "Cert")

    admin.site.unregister(Ca)
    admin.site.unregister(Cert)


    @admin.register(Ca)
    class CaAdmin(BaseCaAdmin):
        pass
        # add your changes here


    @admin.register(Cert)
    class CertAdmin(BaseCertAdmin):
        pass
        # add your changes here

``sample_subnet_division``
++++++++++++++++++++++++++

.. code-block:: python

    from openwisp_controller.subnet_division.admin import (
        SubnetAdmin as BaseSubnetAdmin,
        IpAddressAdmin as BaseIpAddressAdmin,
        SubnetDivisionRuleInlineAdmin as BaseSubnetDivisionRuleInlineAdmin,
    )
    from django.contrib import admin
    from swapper import load_model

    Subnet = load_model("openwisp_ipam", "Subnet")
    IpAddress = load_model("openwisp_ipam", "IpAddress")
    SubnetDivisionRule = load_model("subnet_division", "SubnetDivisionRule")

    admin.site.unregister(Subnet)
    admin.site.unregister(IpAddress)
    admin.site.unregister(SubnetDivisionRule)


    @admin.register(Subnet)
    class SubnetAdmin(BaseSubnetAdmin):
        pass
        # add your changes here


    @admin.register(IpAddress)
    class IpAddressAdmin(BaseIpAddressAdmin):
        pass
        # add your changes here


    @admin.register(SubnetDivisionRule)
    class SubnetDivisionRuleInlineAdmin(BaseSubnetDivisionRuleInlineAdmin):
        pass
        # add your changes here

15. Create Root URL Configuration
---------------------------------

.. code-block:: python

    from django.contrib import admin
    from openwisp_controller.config.utils import get_controller_urls
    from openwisp_controller.geo.utils import get_geo_urls

    # from .sample_config import views as config_views
    # from .sample_geo import views as geo_views

    urlpatterns = [
        # ... other urls in your project ...
        # Use only when changing controller API views (discussed below)
        # url(r'^controller/', include((get_controller_urls(config_views), 'controller'), namespace='controller'))
        # Use only when changing geo API views (discussed below)
        # url(r'^geo/', include((get_geo_urls(geo_views), 'geo'), namespace='geo')),
        # openwisp-controller urls
        url(
            r"",
            include(
                ("openwisp_controller.config.urls", "config"),
                namespace="config",
            ),
        ),
        url(r"", include("openwisp_controller.urls")),
    ]

For more information about URL configuration in django, please refer to
the `"URL dispatcher" section in the django documentation
<https://docs.djangoproject.com/en/4.2/topics/http/urls/>`_.

16. Import the Automated Tests
------------------------------

When developing a custom application based on this module, it's a good
idea to import and run the base tests too, so that you can be sure the
changes you're introducing are not breaking some of the existing features
of *OpenWISP Controller*.

In case you need to add breaking changes, you can overwrite the tests
defined in the base classes to test your own behavior.

See the tests in sample_app to find out how to do this.

- `project common tests.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/tests.py>`_
- `sample_config tests.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/tests.py>`_
- `sample_geo tests.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/tests.py>`_
- `sample_geo pytest.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/pytest.py>`_
- `sample_pki tests.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_pki/tests.py>`_
- `sample_connection tests.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_connection/tests.py>`_
- `sample_subnet_division tests.py
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_subnet_division/tests.py>`_

For running the tests, you need to copy fixtures as well:

- Change `sample_config` to your config app's name in `sample_config
  fixtures
  <https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/fixtures/>`_
  and paste it in the ``sample_config/fixtures/`` directory.

You can then run tests with:

.. code-block:: bash

    # the --parallel flag is optional
    ./manage.py test --parallel mycontroller

Substitute ``mycontroller`` with the name you chose in step 1.

For more information about automated tests in django, please refer to
`"Testing in Django"
<https://docs.djangoproject.com/en/4.2/topics/testing/>`_.

Other Base Classes that Can Be Inherited and Extended
-----------------------------------------------------

The following steps are not required and are intended for more advanced
customization.

1. Extending the Controller API Views
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Extending the `sample_config/views.py
<https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_config/views.py>`_
is required only when you want to make changes in the controller API,
Remember to change ``config_views`` location in ``urls.py`` in point 11
for extending views.

For more information about django views, please refer to the `views
section in the django documentation
<https://docs.djangoproject.com/en/4.2/topics/http/views/>`_.

2. Extending the Geo API Views
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Extending the `sample_geo/views.py
<https://github.com/openwisp/openwisp-controller/tree/master/tests/openwisp2/sample_geo/views.py>`_
is required only when you want to make changes in the geo API, Remember to
change ``geo_views`` location in ``urls.py`` in point 11 for extending
views.

For more information about django views, please refer to the `views
section in the django documentation
<https://docs.djangoproject.com/en/4.2/topics/http/views/>`_.

.. _custom_subnet_division_rule_types:

Custom Subnet Division Rule Types
---------------------------------

It is possible to create your own :doc:`subnet division rule types
<../user/subnet-division-rules>`. The rule type determines when subnets
and IPs will be provisioned and when they will be destroyed.

You can create your custom rule types by extending
``openwisp_controller.subnet_division.rule_types.base.BaseSubnetDivisionRuleType``.

Below is an example to create a subnet division rule type that will
provision subnets and IPs when a new device is created and will delete
them upon deletion for that device.

.. code-block:: python

    # In mycontroller/sample_subnet_division/rules_types/custom.py

    from django.db.models.signals import post_delete, post_save
    from swapper import load_model

    from openwisp_controller.subnet_division.rule_types.base import (
        BaseSubnetDivisionRuleType,
    )

    Device = load_model("config", "Device")


    class CustomRuleType(BaseSubnetDivisionRuleType):
        # The signal on which provisioning should be triggered
        provision_signal = post_save
        # The sender of the provision_signal
        provision_sender = Device
        # Dispatch UID for connecting provision_signal to provision_receiver
        provision_dispatch_uid = "some_unique_identifier_string"

        # The signal on which deletion should be triggered
        destroyer_signal = post_delete
        # The sender of the destroyer_signal
        destroyer_sender = Device
        # Dispatch UID for connecting destroyer_signal to destroyer_receiver
        destroyer_dispatch_uid = "another_unique_identifier_string"

        # Attribute path to organization_id
        # Example 1: If organization_id is direct attribute of provision_signal
        #            sender instance, then
        #   organization_id_path = 'organization_id'
        # Example 2: If organization_id is indirect attribute of provision signal
        #            sender instance, then
        #   organization_id_path = 'some_attribute.another_intermediate.organization_id'
        organization_id_path = "organization_id"

        # Similar to organization_id_path but for the required subnet attribute
        subnet_path = "subnet"

        # An intermediate method through which you can specify conditions for provisions
        @classmethod
        def should_create_subnets_ips(cls, instance, **kwargs):
            # Using "post_save" provision_signal, the rule should be only
            # triggered when a new object is created.
            return kwargs["created"]

        # You can define logic to trigger provisioning for existing objects
        # using following classmethod. By default, BaseSubnetDivisionRuleType
        # performs no operation for existing objects.
        @classmethod
        def provision_for_existing_objects(cls, rule_obj):
            for device in Device.objects.filter(organization=rule_obj.organization):
                cls.provision_receiver(device, created=True)

After creating a class for your custom rule type, you will need to set
:ref:`OPENWISP_CONTROLLER_SUBNET_DIVISION_TYPES
<OPENWISP_CONTROLLER_SUBNET_DIVISION_TYPES>` setting as follows:

.. code-block:: python

    OPENWISP_CONTROLLER_SUBNET_DIVISION_TYPES = (
        (
            "openwisp_controller.subnet_division.rule_types.vpn.VpnSubnetDivisionRuleType",
            "VPN",
        ),
        (
            "openwisp_controller.subnet_division.rule_types.device.DeviceSubnetDivisionRuleType",
            "Device",
        ),
        (
            "mycontroller.sample_subnet_division.rules_types.custom.CustomRuleType",
            "Custom Rule",
        ),
    )

More Utilities to Extend OpenWISP Controller
--------------------------------------------

See :doc:`utils`.
