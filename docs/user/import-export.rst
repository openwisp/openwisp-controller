Import/Export Device Data
=========================

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.1/import-export/device-list.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.1/import-export/device-list.png
    :alt: Import / Export

The device list page offers two buttons to export and import device data
in different formats.

Importing
---------

For importing devices into the system, only the required fields are
needed, for example, the following CSV file will import a device named
``TestImport`` with mac address ``00:11:22:09:44:55`` in the organization
with UUID ``3cb5e18c-0312-48ab-8dbd-038b8415bd6f``:

.. code-block::

    organization,name,mac_address
    3cb5e18c-0312-48ab-8dbd-038b8415bd6f,TestImport,00:11:22:09:44:55

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.1/import-export/import-page.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.1/import-export/import-page.png
    :alt: Import / Export

Exporting
---------

The export feature respects any filters selected in the device list.

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.1/import-export/export-page.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-controller/docs/docs/1.1/import-export/export-page.png
    :alt: Export
