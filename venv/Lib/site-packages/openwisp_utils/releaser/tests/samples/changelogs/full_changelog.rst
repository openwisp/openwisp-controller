Changelog
=========

[unreleased]
------------

Features
~~~~~~~~

- ValidatedModelSerializer: added exclude_validation, don't set m2m
- Added retry mechanism to SeleniumTestMixin `#464
  <https://github.com/#REPO#/issues/464>`_
- Generate CHANGES.rst automatically `#496
  <https://github.com/#REPO#/issues/496>`_

Changes
~~~~~~~

Backward-incompatible changes
+++++++++++++++++++++++++++++

- Dropped support for OPENWISP_EMAIL_TEMPLATE setting `#482
  <https://github.com/#REPO#/issues/482>`_

Other changes
+++++++++++++

- Use docstrfmt for checking ReStructuredText files
- Rollback DRF to 3.15 (security)
- Switched to prettier for CSS/JS linting `#367
  <https://github.com/#REPO#/issues/367>`_

Dependencies
++++++++++++

- Bumped ``djangorestframework<3.16.1``
- Bumped ``pytest-asyncio<0.27``
- Bumped ``selenium<4.35``
- Bumped ``swapper~=1.4.0``
- Updated QA dependencies

Bugfixes
~~~~~~~~

- Fixed padding of the email container
- Fixed the recipient string in email template
- Fixed the height of the logo in email template
