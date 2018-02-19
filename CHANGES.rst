Changelog
=========

Version 0.3.2 [2018-02-19]
--------------------------

- [requirements] Updated requirements and added support for django 2.0

Version 0.3.1 [2017-12-20]
--------------------------

- [pki] Reimplemented serial numbers as UUID integers
- [pki] Added switcher that facilitates importing certificates
- [pki] [admin] Removed ``serial_number`` from certificate list

Version 0.3.0 [2017-12-17]
--------------------------

- [feature] Added geographic and indoor mapping module
- [feature] Aded Dockerfile

Version 0.2.5 [2017-12-02]
--------------------------

- `#21 <https://github.com/openwisp/openwisp-controller/issues/21>`_:
  [admin] Added a link to password reset in login form

Version 0.2.4 [2017-11-07]
--------------------------

- Added support for django-x509 0.3.0

Version 0.2.3 [2017-08-29]
--------------------------

- `934be13 <https://github.com/openwisp/openwisp-controller/commit/934be13>`_:
  [models] Updated sortedm2m __str__ definition
- `b76e4e2 <https://github.com/openwisp/openwisp-controller/commit/b76e4e2>`_:
  [requirements] django-netjsonconfig>=0.6.3,<0.7.0

Version 0.2.2 [2017-07-10]
--------------------------

- `f3dc784 <https://github.com/openwisp/openwisp-controller/commit/f3dc784>`_:
  [admin] Moved ``submit_line.html`` to `openwisp-utils
  <https://github.com/openwisp/openwisp-utils>`_

Version 0.2.1 [2017-07-05]
--------------------------

- `0064b98 <https://github.com/openwisp/openwisp-controller/commit/0064b98>`_:
  [device] Added ``system`` field
- `c7fe513 <https://github.com/openwisp/openwisp-controller/commit/c7fe513>`_:
  [docs] Added "Installing for development" section to README
- `c75fa68 <https://github.com/openwisp/openwisp-controller/commit/c75fa68>`_:
  [openwisp-utils] Moved shared logic to `openwisp-utils
  <https://github.com/openwisp/openwisp-utils>`_
- `819cb21 <https://github.com/openwisp/openwisp-controller/commit/819cb21>`_:
  [requirements] django-netjsonconfig>=0.6.2,<0.7.0

Version 0.2.0 [2017-05-24]
--------------------------

- `#3 <https://github.com/openwisp/openwisp-controller/issues/3>`_:
  [feature] Added support for template tags
- `#7 <https://github.com/openwisp/openwisp-controller/issues/7>`_:
  [feature] Added ``Device`` model
- `#9 <https://github.com/openwisp/openwisp-controller/issues/9>`_:
  [admin] Load default templates JS logic only when required
- `298b2a2 <https://github.com/openwisp/openwisp-controller/commit/298b2a2>`_:
  [admin] Avoid setting ``extra_content`` to mutable object
- `d173c24 <https://github.com/openwisp/openwisp-controller/commit/d173c24>`_:
  [migrations] Squashed ``0001`` and ``0002`` to avoid postgres error
- `f5fb628 <https://github.com/openwisp/openwisp-controller/commit/f5fb628>`_:
  [migrations] Updated indexes
- `6200b7a <https://github.com/openwisp/openwisp-controller/commit/6200b7a>`_:
  [Template] Fixed ``auto_client`` bug

Version 0.1.4 [2017-04-21]
--------------------------

- `#2 <https://github.com/openwisp/openwisp-controller/issues/2>`_:
  [admin] Added templates in config filter

Version 0.1.3 [2017-03-11]
--------------------------

- `db77ae7 <https://github.com/openwisp/openwisp-controller/commit/db77ae7>`_:
  [controller] Added "error: " prefix in error responses

Version 0.1.2 [2017-03-15]
--------------------------

- `3c61053 <https://github.com/openwisp/openwisp-controller/commit/3c61053>`_:
  [admin] Ensure preview button is present
- `0087483 <https://github.com/openwisp/openwisp-controller/commit/0087483>`_:
  [models] Converted ``OrganizationConfigSettings`` to UUID primary key

Version 0.1.1 [2017-03-10]
--------------------------

- `cbca4e1 <https://github.com/openwisp/openwisp-controller/commit/cbca4e1>`_:
  [users] Fixed integration with `openwisp-users <https://github.com/openwisp/openwisp-users>`_

Version 0.1.0 [2017-03-08]
--------------------------

- added multi-tenancy (separation of organizations) to `openwisp2 <http://openwisp.org>`_
- added email confirmation of new users (via `django-allauth <http://www.intenct.nl/projects/django-allauth/>`_)
