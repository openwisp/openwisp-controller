REST API Reference
==================

.. contents:: **Table of contents**:
    :depth: 1
    :local:

.. _controller_live_documentation:

Live Documentation
------------------

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/live-docu-api.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/live-docu-api.png

A general live API documentation (following the OpenAPI specification) at
``/api/v1/docs/``.

.. _controller_browsable_web_interface:

Browsable Web Interface
-----------------------

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/browsable-api-ui.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/browsable-api-ui.png

Additionally, opening any of the endpoints :ref:`listed below
<controller_rest_endpoints>` directly in the browser will show the
`browsable API interface of Django-REST-Framework
<https://www.django-rest-framework.org/topics/browsable-api/>`_, which
makes it even easier to find out the details of each endpoint.

Authentication
--------------

See :ref:`authenticating_rest_api`.

When browsing the API via the :ref:`controller_live_documentation` or the
:ref:`controller_browsable_web_interface`, you can also use the session
authentication by logging in the django admin.

Pagination
----------

All *list* endpoints support the ``page_size`` parameter that allows
paginating the results in conjunction with the ``page`` parameter.

.. code-block:: text

    GET /api/v1/controller/template/?page_size=10
    GET /api/v1/controller/template/?page_size=10&page=2

.. _controller_rest_endpoints:

List of Endpoints
-----------------

Since the detailed explanation is contained in the
:ref:`controller_live_documentation` and in the
:ref:`controller_browsable_web_interface` of each point, here we'll
provide just a list of the available endpoints, for further information
please open the URL of the endpoint in your browser.

List Devices
~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/device/

**Available filters**

You can filter a list of devices based on their configuration status using
the ``status`` (e.g modified, applied, or error).

.. code-block:: text

    GET /api/v1/controller/device/?config__status={status}

You can filter a list of devices based on their configuration backend
using the ``backend`` (e.g ``netjsonconfig.OpenWrt`` or
``netjsonconfig.OpenWisp``).

.. code-block:: text

    GET /api/v1/controller/device/?config__backend={backend}

You can filter a list of devices based on their organization using the
``organization_id`` or ``organization_slug``.

.. code-block:: text

    GET /api/v1/controller/device/?organization={organization_id}

.. code-block:: text

    GET /api/v1/controller/device/?organization_slug={organization_slug}

You can filter a list of devices based on their configuration templates
using the ``template_id``.

.. code-block:: text

    GET /api/v1/controller/device/?config__templates={template_id}

You can filter a list of devices based on their device group using the
``group_id``.

.. code-block:: text

    GET /api/v1/controller/device/?group={group_id}

You can filter a list of devices that have a device location object using
the ``with_geo`` (e.g. true or false).

.. code-block:: text

    GET /api/v1/controller/device/?with_geo={with_geo}

You can filter a list of devices based on their creation time using the
``creation_time``.

.. code-block:: text

    # Created exact
    GET /api/v1/controller/device/?created={creation_time}

    # Created greater than or equal to
    GET /api/v1/controller/device/?created__gte={creation_time}

    # Created is less than
    GET /api/v1/controller/device/?created__lt={creation_time}

Create Device
~~~~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/device/

Get Device Detail
~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/device/{id}/

Download Device Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/device/{id}/configuration/

The above endpoint triggers the download of a ``tar.gz`` file containing
the generated configuration for that specific device.

Change Details of Device
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PUT /api/v1/controller/device/{id}/

Patch Details of Device
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PATCH /api/v1/controller/device/{id}/

.. note::

    To assign, unassign, and change the order of the assigned templates
    add, remove, and change the order of the ``{id}`` of the templates
    under the ``config`` field in the JSON response respectively.
    Moreover, you can also select and unselect templates in the HTML Form
    of the Browsable API.

The required template(s) from the organization(s) of the device will added
automatically to the ``config`` and cannot be removed.

**Example usage**: For assigning template(s) add the/their {id} to the
config of a device,

.. code-block:: shell

    curl -X PATCH \
        http://127.0.0.1:8000/api/v1/controller/device/76b7d9cc-4ffd-4a43-b1b0-8f8befd1a7c0/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'content-type: application/json' \
        -d '{
                "config": {
                    "templates": ["4791fa4c-2cef-4f42-8bb4-c86018d71bd3"]
                }
            }'

**Example usage**: For removing assigned templates, simply remove
the/their {id} from the config of a device,

.. code-block:: shell

    curl -X PATCH \
        http://127.0.0.1:8000/api/v1/controller/device/76b7d9cc-4ffd-4a43-b1b0-8f8befd1a7c0/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'content-type: application/json' \
        -d '{
                "config": {
                    "templates": []
                }
            }'

**Example usage**: For reordering the templates simply change their order
from the config of a device,

.. code-block:: shell

    curl -X PATCH \
        http://127.0.0.1:8000/api/v1/controller/device/76b7d9cc-4ffd-4a43-b1b0-8f8befd1a7c0/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'cache-control: no-cache' \
        -H 'content-type: application/json' \
        -H 'postman-token: b3f6a1cc-ff13-5eba-e460-8f394e485801' \
        -d '{
                "config": {
                    "templates": [
                        "c5bbc697-170e-44bc-8eb7-b944b55ee88f",
                        "4791fa4c-2cef-4f42-8bb4-c86018d71bd3"
                    ]
                }
            }'

Delete Device
~~~~~~~~~~~~~

.. note::

    A device must be deactivated before it can be deleted. Otherwise, an
    ``HTTP 403 Forbidden`` response will be returned.

.. code-block:: text

    DELETE /api/v1/controller/device/{id}/

Deactivate Device
~~~~~~~~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/device/{id}/deactivate/

Activate Device
~~~~~~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/device/{id}/activate/

List Device Connections
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/device/{id}/connection/

Create Device Connection
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/device/{id}/connection/

Get Device Connection Detail
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/device/{id}/connection/{id}/

Change Device Connection Detail
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PUT /api/v1/controller/device/{id}/connection/{id}/

Patch Device Connection Detail
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PATCH /api/v1/controller/device/{id}/connection/{id}/

Delete Device Connection
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    DELETE /api/v1/controller/device/{id}/connection/{id}/

List Credentials
~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/connection/credential/

Create Credential
~~~~~~~~~~~~~~~~~

.. code-block:: text

    POST /api/v1/connection/credential/

Get Credential Detail
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/connection/credential/{id}/

Change Credential Detail
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PUT /api/v1/connection/credential/{id}/

Patch Credential Detail
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PATCH /api/v1/connection/credential/{id}/

Delete Credential
~~~~~~~~~~~~~~~~~

.. code-block:: text

    DELETE /api/v1/connection/credential/{id}/

List Commands of a Device
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/device/{id}/command/

Execute a Command a Device
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/device/{id}/command/

Get Command Details
~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/device/{device_id}/command/{command_id}/

List Device Groups
~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/group/

**Available filters**

You can filter a list of device groups based on their organization using
the ``organization_id`` or ``organization_slug``.

.. code-block:: text

    GET /api/v1/controller/group/?organization={organization_id}

.. code-block:: text

    GET /api/v1/controller/group/?organization_slug={organization_slug}

You can filter a list of device groups that have a device object using the
``empty`` (e.g. true or false).

.. code-block:: text

    GET /api/v1/controller/group/?empty={empty}

Create Device Group
~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/group/

Get Device Group Detail
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/group/{id}/

.. _change_device_group_detail:

Change Device Group Detail
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PUT /api/v1/controller/group/{id}/

This endpoint allows to change the :ref:`device_group_templates` too.

Get Device Group from Certificate Common Name
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/cert/{common_name}/group/

This endpoint can be used to retrieve group information and metadata by
the common name of a certificate used in a VPN client tunnel, this
endpoint is used in layer 2 tunneling solutions for firewall/captive
portals.

It is also possible to filter device group by providing organization slug
of certificate's organization as show in the example below:

.. code-block:: text

    GET /api/v1/controller/cert/{common_name}/group/?org={org1_slug},{org2_slug}

Get Device Location
~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/device/{id}/location/

.. _create_device_location:

Create Device Location
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PUT /api/v1/controller/device/{id}/location/

You can create ``DeviceLocation`` object by using primary keys of existing
``Location`` and ``FloorPlan`` objects as shown in the example below.

.. code-block:: json

    {
        "location": "f0cb5762-3711-4791-95b6-c2f6656249fa",
        "floorplan": "dfeb6724-aab4-4533-aeab-f7feb6648acd",
        "indoor": "-36,264"
    }

.. note::

    The ``indoor`` field represents the coordinates of the point placed on
    the image from the top left corner. E.g. if you placed the pointer on
    the top left corner of the floor plan image, its indoor coordinates
    will be ``0,0``.

.. code-block:: text

    curl -X PUT \
        http://127.0.0.1:8000/api/v1/controller/device/8a85cc23-bad5-4c7e-b9f4-ffe298defb5c/location/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'content-type: application/json' \
        -d '{
            "location": "f0cb5762-3711-4791-95b6-c2f6656249fa",
            "floorplan": "dfeb6724-aab4-4533-aeab-f7feb6648acd",
            "indoor": "-36,264"
            }'

You can also create related ``Location`` and ``FloorPlan`` objects for the
device directly from this endpoint.

The following example demonstrates creating related location object in a
single request.

.. code-block:: json

    {
        "location": {
            "name": "Via del Corso",
            "address": "Via del Corso, Roma, Italia",
            "geometry": {
                "type": "Point",
                "coordinates": [12.512124, 41.898903]
            },
            "type": "outdoor",
        }
    }

.. code-block:: text

    curl -X PUT \
        http://127.0.0.1:8000/api/v1/controller/device/8a85cc23-bad5-4c7e-b9f4-ffe298defb5c/location/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'content-type: application/json' \
        -d '{
                "location": {
                    "name": "Via del Corso",
                    "address": "Via del Corso, Roma, Italia",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [12.512124, 41.898903]
                    },
                    "type": "outdoor"
                }
            }'

.. note::

    You can also specify the ``geometry`` in **Well-known text (WKT)**
    format, like following:

    .. code-block:: json

        {
            "location": {
                "name": "Via del Corso",
                "address": "Via del Corso, Roma, Italia",
                "geometry": "POINT (12.512124 41.898903)",
                "type": "outdoor",
            }
        }

Similarly, you can create ``Floorplan`` object with the same request. But,
note that a ``FloorPlan`` can be added to ``DeviceLocation`` only if the
related ``Location`` object defines an indoor location. The example below
demonstrates creating both ``Location`` and ``FloorPlan`` objects.

.. code-block:: json

    {
        "location.name": "Via del Corso",
        "location.address": "Via del Corso, Roma, Italia",
        "location.geometry.type": "Point",
        "location.geometry.coordinates": [12.512124, 41.898903],
        "location.type": "outdoor",
        "floorplan.floor": 1,
        "floorplan.image": "floorplan.png"
    }

.. code-block:: text

    curl -X PUT \
        http://127.0.0.1:8000/api/v1/controller/device/8a85cc23-bad5-4c7e-b9f4-ffe298defb5c/location/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'content-type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW' \
        -F 'location.name=Via del Corso' \
        -F 'location.address=Via del Corso, Roma, Italia' \
        -F location.geometry.type=Point \
        -F 'location.geometry.coordinates=[12.512124, 41.898903]' \
        -F location.type=indoor \
        -F floorplan.floor=1 \
        -F 'floorplan.image=@floorplan.png'

.. note::

    The example above uses ``multipart content-type`` for uploading floor
    plan image.

You can also use an existing ``Location`` object and create a new floor
plan for that location using this endpoint.

.. code-block:: json

    {
        "location": "f0cb5762-3711-4791-95b6-c2f6656249fa",
        "floorplan.floor": 1,
        "floorplan.image": "floorplan.png"
    }

.. code-block:: text

    curl -X PUT \
        http://127.0.0.1:8000/api/v1/controller/device/8a85cc23-bad5-4c7e-b9f4-ffe298defb5c/location/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'content-type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW' \
        -F location=f0cb5762-3711-4791-95b6-c2f6656249fa \
        -F floorplan.floor=1 \
        -F 'floorplan.image=@floorplan.png'

Change Details of Device Location
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PUT /api/v1/controller/device/{id}/location/

.. note::

    This endpoint can be used to update related ``Location`` and
    ``Floorplan`` objects. Refer to the :ref:`examples in the "Create
    device location" section <create_device_location>` for information on
    payload format.

Delete Device Location
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    DELETE /api/v1/controller/device/{id}/location/

Get Device Coordinates
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/device/{id}/coordinates/

.. note::

    This endpoint is intended to be used by devices.

This endpoint skips multi-tenancy and permission checks if the device
``key`` is passed as ``query_param`` because the system assumes that the
device is updating it's position.

.. code-block:: text

    curl -X GET \
        'http://127.0.0.1:8000/api/v1/controller/device/8a85cc23-bad5-4c7e-b9f4-ffe298defb5c/coordinates/?key=10a0cb5a553c71099c0e4ef236435496'

Update Device Coordinates
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PUT /api/v1/controller/device/{id}/coordinates/

.. note::

    This endpoint is intended to be used by devices.

This endpoint skips multi-tenancy and permission checks if the device
``key`` is passed as ``query_param`` because the system assumes that the
device is updating it's position.

.. code-block:: json

    {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [12.512124, 41.898903]
        },
    }

.. code-block:: text

    curl -X PUT \
        'http://127.0.0.1:8000/api/v1/controller/device/8a85cc23-bad5-4c7e-b9f4-ffe298defb5c/coordinates/?key=10a0cb5a553c71099c0e4ef236435496' \
        -H 'content-type: application/json' \
        -d '{
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [12.512124, 41.898903]
                },
            }'

List Locations
~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/location/

**Available filters**

You can filter using ``organization_id`` or ``organization_slug`` to get
list locations that belongs to an organization.

.. code-block:: text

    GET /api/v1/controller/location/?organization={organization_id}

.. code-block:: text

    GET /api/v1/controller/location/?organization_slug={organization_slug}

Create Location
~~~~~~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/location/

If you are creating an ``indoor`` location, you can use this endpoint to
create floor plan for the location.

The following example demonstrates creating floor plan along with location
in a single request.

.. code-block:: json

    {
        "name": "Via del Corso",
        "address": "Via del Corso, Roma, Italia",
        "geometry.type": "Point",
        "geometry.location": [12.512124, 41.898903],
        "type": "indoor",
        "is_mobile": "false",
        "floorplan.floor": "1",
        "floorplan.image": "floorplan.png",
        "organization": "1f6c5666-1011-4f1d-bce9-fc6fcb4f3a05"
    }

.. code-block:: text

    curl -X POST \
        http://127.0.0.1:8000/api/v1/controller/location/ \
        -H 'authorization: Bearer dc8d497838d4914c9db9aad9b6ec66f6c36ff46b' \
        -H 'content-type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW' \
        -F 'name=Via del Corso' \
        -F 'address=Via del Corso, Roma, Italia' \
        -F geometry.type=Point \
        -F 'geometry.coordinates=[12.512124, 41.898903]' \
        -F type=indoor \
        -F is_mobile=false \
        -F floorplan.floor=1 \
        -F 'floorplan.image=@floorplan.png' \
        -F organization=1f6c5666-1011-4f1d-bce9-fc6fcb4f3a05

.. note::

    You can also specify the ``geometry`` in **Well-known text (WKT)**
    format, like following:

.. code-block:: json

    {
        "name": "Via del Corso",
        "address": "Via del Corso, Roma, Italia",
        "geometry": "POINT (12.512124 41.898903)",
        "type": "indoor",
        "is_mobile": "false",
        "floorplan.floor": "1",
        "floorplan.image": "floorplan.png",
        "organization": "1f6c5666-1011-4f1d-bce9-fc6fcb4f3a05"
    }

Get Location Details
~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/location/{pk}/

Change Location Details
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PUT /api/v1/controller/location/{pk}/

.. note::

    Only the first floor plan data present can be edited or changed.
    Setting the ``type`` of location to outdoor will remove all the floor
    plans associated with it.

Refer to the :ref:`examples in the "Create device location" section
<create_device_location>` for information on payload format.

Delete Location
~~~~~~~~~~~~~~~

.. code-block:: text

    DELETE /api/v1/controller/location/{pk}/

List Devices in a Location
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/location/{id}/device/

List Locations with Devices Deployed (in GeoJSON Format)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::

    this endpoint will only list locations that have been assigned to a
    device.

.. code-block:: text

    GET /api/v1/controller/location/geojson/

**Available filters**

You can filter using ``organization_id`` or ``organization_slug`` to get
list location of devices from that organization.

.. code-block:: text

    GET /api/v1/controller/location/geojson/?organization_id={organization_id}

.. code-block:: text

    GET /api/v1/controller/location/geojson/?organization_slug={organization_slug}

Floor Plan List
~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/floorplan/

**Available filters**

You can filter using ``organization_id`` or ``organization_slug`` to get
list floor plans that belongs to an organization.

.. code-block:: text

    GET /api/v1/controller/floorplan/?organization={organization_id}

.. code-block:: text

    GET /api/v1/controller/floorplan/?organization_slug={organization_slug}

Create Floor Plan
~~~~~~~~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/floorplan/

Get Floor Plan Details
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/floorplan/{pk}/

Change Floor Plan Details
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PUT /api/v1/controller/floorplan/{pk}/

Delete Floor Plan
~~~~~~~~~~~~~~~~~

.. code-block:: text

    DELETE /api/v1/controller/floorplan/{pk}/

List Templates
~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/template/

**Available filters**

You can filter a list of templates based on their organization using the
``organization_id`` or ``organization_slug``.

.. code-block:: text

    GET /api/v1/controller/template/?organization={organization_id}

.. code-block:: text

    GET /api/v1/controller/template/?organization_slug={organization_slug}

You can filter a list of templates based on their backend using the
``backend`` (e.g ``netjsonconfig.OpenWrt`` or ``netjsonconfig.OpenWisp``).

.. code-block:: text

    GET /api/v1/controller/template/?backend={backend}

You can filter a list of templates based on their type using the ``type``
(e.g. vpn or generic).

.. code-block:: text

    GET /api/v1/controller/template/?type={type}

You can filter a list of templates that are enabled by default or not
using the ``default`` (e.g. true or false).

.. code-block:: text

    GET /api/v1/controller/template/?default={default}

You can filter a list of templates that are required or not using the
``required`` (e.g. true or false).

.. code-block:: text

    GET /api/v1/controller/template/?required={required}

You can filter a list of templates based on their creation time using the
``creation_time``.

.. code-block:: text

    # Created exact

    GET /api/v1/controller/template/?created={creation_time}

    # Created greater than or equal to

    GET /api/v1/controller/template/?created__gte={creation_time}

    # Created is less than

    GET /api/v1/controller/template/?created__lt={creation_time}

Create Template
~~~~~~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/template/

Get Template Detail
~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/template/{id}/

Download Template Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/template/{id}/configuration/

The above endpoint triggers the download of a ``tar.gz`` file containing
the generated configuration for that specific template.

Change Details of Template
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PUT /api/v1/controller/template/{id}/

Patch Details of Template
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PATCH /api/v1/controller/template/{id}/

Delete Template
~~~~~~~~~~~~~~~

.. code-block:: text

    DELETE /api/v1/controller/template/{id}/

List VPNs
~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/vpn/

**Available filters**

You can filter a list of vpns based on their backend using the ``backend``
(e.g ``openwisp_controller.vpn_backends.OpenVpn`` or
``openwisp_controller.vpn_backends.Wireguard``).

.. code-block:: text

    GET /api/v1/controller/vpn/?backend={backend}

You can filter a list of vpns based on their subnet using the
``subnet_id``.

.. code-block:: text

    GET /api/v1/controller/vpn/?subnet={subnet_id}

You can filter a list of vpns based on their organization using the
``organization_id`` or ``organization_slug``.

.. code-block:: text

    GET /api/v1/controller/vpn/?organization={organization_id}

.. code-block:: text

    GET /api/v1/controller/vpn/?organization_slug={organization_slug}

Create VPN
~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/vpn/

Get VPN detail
~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/vpn/{id}/

Download VPN Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/vpn/{id}/configuration/

The above endpoint triggers the download of a ``tar.gz`` file containing
the generated configuration for that specific VPN.

Change Details of VPN
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PUT /api/v1/controller/vpn/{id}/

Patch Details of VPN
~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PATCH /api/v1/controller/vpn/{id}/

Delete VPN
~~~~~~~~~~

.. code-block:: text

    DELETE /api/v1/controller/vpn/{id}/

List CA
~~~~~~~

.. code-block:: text

    GET /api/v1/controller/ca/

Create New CA
~~~~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/ca/

Import Existing CA
~~~~~~~~~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/ca/

.. note::

    To import an existing CA, only ``name``, ``certificate`` and
    ``private_key`` fields have to be filled in the ``HTML`` form or
    included in the ``JSON`` format.

Get CA Detail
~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/ca/{id}/

Change Details of CA
~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PUT /api/v1/controller/ca/{id}/

Patch Details of CA
~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PATCH /api/v1/controller/ca/{id}/

Download CA(crl)
~~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/ca/{id}/crl/

The above endpoint triggers the download of ``{id}.crl`` file containing
up to date CRL of that specific CA.

Delete CA
~~~~~~~~~

.. code-block:: text

    DELETE /api/v1/controller/ca/{id}/

Renew CA
~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/ca/{id}/renew/

List Cert
~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/cert/

Create New Cert
~~~~~~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/cert/

Import Existing Cert
~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/cert/

.. note::

    To import an existing Cert, only ``name``, ``ca``, ``certificate`` and
    ``private_key`` fields have to be filled in the ``HTML`` form or
    included in the ``JSON`` format.

Get Cert Detail
~~~~~~~~~~~~~~~

.. code-block:: text

    GET /api/v1/controller/cert/{id}/

Change Details of Cert
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PUT /api/v1/controller/cert/{id}/

Patch Details of Cert
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    PATCH /api/v1/controller/cert/{id}/

Delete Cert
~~~~~~~~~~~

.. code-block:: text

    DELETE /api/v1/controller/cert/{id}/

Renew Cert
~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/cert/{id}/renew/

Revoke Cert
~~~~~~~~~~~

.. code-block:: text

    POST /api/v1/controller/cert/{id}/revoke/
