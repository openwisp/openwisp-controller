X.509 Certificate Generator Templates
=====================================

.. contents:: **Table of Contents**:
    :depth: 3
    :local:

Introduction
------------

A Certificate Template is a specific type of :doc:`Configuration Template
</controller/user/templates>` that allows OpenWISP to centrally manage and
automatically provision X.509 client certificates for devices.

Unlike VPN templates, which generate certificates as part of a larger
tunnel configuration (like OpenVPN or WireGuard), Certificate Templates
are standalone. They are ideal for use cases where devices need
cryptographic identities for external services, such as:

- Mutual TLS (mTLS) authentication against internal APIs.
- Cryptographically signed device identities for 802.1x or captive
  portals.
- Secure payload signing.

.. _certificate_templates_setup:

Setting Up a Certificate Template
---------------------------------

To create a Certificate Template, navigate to the Templates section in the
OpenWISP admin and set the **Type** to :guilabel:`Certificate` (``cert``).
This will reveal the certificate-specific configuration fields.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/certificate-template.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/certificate-template.png
    :alt: Certificate Template admin form

:guilabel:`Certificate Authority` (required)
    The Certificate Authority that will sign the X.509 certificates
    generated for each device using the template. The CA must belong to
    the same organization as the template (or be shared).

:guilabel:`Blueprint Certificate` (optional)
    An existing, unassigned, non-revoked X.509 certificate that will be
    used as a *blueprint*. The extensions, key length, digest, and other
    subject fields of the blueprint are copied to each newly generated
    certificate. The blueprint must be signed by the selected
    :guilabel:`Certificate Authority` and must not already be bound to a
    device.

:guilabel:`Automatic certificate provisioning` (``auto_cert``)
    When enabled (which is the default behavior), an X.509 certificate is
    automatically created and signed by the template's CA the moment the
    template is assigned to a device configuration.

.. _certificate_templates_validation:

Validation Rules
----------------

To ensure cryptographic integrity and prevent misconfigurations,
Certificate Templates enforce the following validation rules upon saving:

- A :guilabel:`Certificate Authority` is strictly required.
- The :guilabel:`Blueprint Certificate` **must** be signed by the selected
  :guilabel:`Certificate Authority`. Saving with a mismatched pair will
  fail.
- The :guilabel:`Blueprint Certificate` must be *unassigned* (it cannot be
  currently bound to any device). The blueprint dropdown in the admin
  panel is pre-filtered to show only unassigned, non-revoked certificates.
- Both the :guilabel:`Certificate Authority` and the :guilabel:`Blueprint
  Certificate` must belong to the same organization as the template, or be
  marked as shared.

.. _certificate_templates_lifecycle:

Provisioning and Revocation Lifecycle
-------------------------------------

Certificate Templates are tightly coupled with the device configuration
lifecycle to ensure certificates are only valid while the device is
actively authorized to use them.

**When assigned to a device:** When a Certificate Template is added to a
device configuration, a ``DeviceCertificate`` relationship is established.
If ``auto_cert`` is enabled, an X.509 certificate is generated and signed
in the same database transaction:

- The certificate's subject and extensions are copied from the
  :guilabel:`Blueprint Certificate` (or the CA defaults).
- The certificate is augmented with two custom OpenWISP OIDs that
  cryptographically identify the device (see
  :ref:`certificate_templates_oid_extensions`).
- The certificate's :guilabel:`Common Name` is generated using the
  :ref:`OPENWISP_CONTROLLER_COMMON_NAME_FORMAT
  <openwisp_controller_common_name_format>` setting, suffixed with a
  unique slug to prevent collisions.

**When removed from a device:** When the Certificate Template is
unassigned from a device configuration, the ``DeviceCertificate``
relationship is deleted. Crucially, the underlying X.509 certificate is
**automatically revoked** (provided it was created via
``auto_cert=True``). This ensures that compromised or decommissioned
devices immediately lose their cryptographic access.

.. _certificate_templates_active_lock:

Active Template Mutation Lock
-----------------------------

To prevent breaking the cryptographic binding with devices that are
already using a template, certain destructive changes are blocked while
the template is assigned to *active* or *activating* device
configurations.

You **cannot** change the following on an actively used template:

- :guilabel:`Type` (only changing a ``cert`` template to a different type
  is blocked)
- :guilabel:`Certificate Authority`
- :guilabel:`Blueprint Certificate`

If you need to update these core parameters, you must first unassign the
Certificate Template from all affected device configurations (or
deactivate the devices), apply your template changes, and then reassign
them.

.. _certificate_templates_oid_extensions:

Custom Device Identification OIDs
---------------------------------

To allow external systems to uniquely and securely identify devices by
parsing their X.509 certificates, every automatically generated
certificate includes two custom ASN.1 Object Identifiers (OIDs):

- ``1.3.6.1.4.1.65901.1``: Contains the MAC address of the device
  (``ASN1:UTF8:string:<mac_address>``).
- ``1.3.6.1.4.1.65901.2``: Contains the UUID of the device
  (``ASN1:UTF8:string:<device_id>``).

These OIDs are appended securely to the certificate in addition to any
extensions inherited from the :guilabel:`Blueprint Certificate`.

.. _certificate_templates_api:

Certificate Templates via the REST API
--------------------------------------

The Certificate Template architecture is fully supported by the
:doc:`OpenWISP REST API </controller/user/rest-api>`:

- The ``type`` field accepts the ``cert`` enumeration.
- ``ca`` and ``blueprint_cert`` are writable fields on the
  ``/api/v1/controller/template/`` endpoint.
- The ``blueprint_cert`` field is strictly filtered. Attempting to pass
  the UUID of an already-assigned or revoked certificate will return a
  ``400 Bad Request``.
- The Active Mutation Lock is enforced at the serializer level: attempting
  to patch the ``type``, ``ca``, or ``blueprint_cert`` of an actively
  deployed template will return a ``400 Bad Request``.

Additionally, you can trigger the automated creation and revocation
lifecycle by patching the ``config.templates`` array on the :ref:`Device
endpoint <rest_device_patch>`.
