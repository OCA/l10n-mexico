==================
Mexico SAT Account
==================

.. 
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! This file is generated by oca-gen-addon-readme !!
   !! changes will be overwritten.                   !!
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! source digest: sha256:9f1266727dfa388f64354de300ba056d6d2c587424c9f708c8db15fbab500ef5
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-OCA%2Fl10n--mexico-lightgray.png?logo=github
    :target: https://github.com/OCA/l10n-mexico/tree/13.0/l10n_mx_sat_account
    :alt: OCA/l10n-mexico
.. |badge4| image:: https://img.shields.io/badge/weblate-Translate%20me-F47D42.png
    :target: https://translation.odoo-community.org/projects/l10n-mexico-13-0/l10n-mexico-13-0-l10n_mx_sat_account
    :alt: Translate me on Weblate
.. |badge5| image:: https://img.shields.io/badge/runboat-Try%20me-875A7B.png
    :target: https://runboat.odoo-community.org/builds?repo=OCA/l10n-mexico&target_branch=13.0
    :alt: Try me on Runboat

|badge1| |badge2| |badge3| |badge4| |badge5|

This module adds a constraint on account to have only one tag from the Mexican tax authority, *Servicio de
Administración Tributaria* (SAT):

http://omawww.sat.gob.mx/contabilidadelectronica/Paginas/03.htm

**Table of contents**

.. contents::
   :local:

Usage
=====

* Go to Accounting > Configuration > Accounting > Chart of Accounts
* For each account, make sure there is a tag whose parent is "SAT"

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/OCA/l10n-mexico/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us to smash it by providing a detailed and welcomed
`feedback <https://github.com/OCA/l10n-mexico/issues/new?body=module:%20l10n_mx_sat_account%0Aversion:%2013.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical issues.

Credits
=======

Authors
~~~~~~~

* Open Source Integrators
* Serpent Consulting Services Pvt. Ltd.

Contributors
~~~~~~~~~~~~

* Open Source Integrators <https://www.opensourceintegrators.com>

  * Maxime Chambreuil <mchambreuil@opensourceintegrators.com>

* Serpent Consulting Services Pvt. Ltd. <https://www.serpentcs.com>

  * Hiren Dangar <hiren.dangar.serpentcs@gmail.com>

Maintainers
~~~~~~~~~~~

This module is maintained by the OCA.

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

.. |maintainer-max3903| image:: https://github.com/max3903.png?size=40px
    :target: https://github.com/max3903
    :alt: max3903

Current `maintainer <https://odoo-community.org/page/maintainer-role>`__:

|maintainer-max3903| 

This module is part of the `OCA/l10n-mexico <https://github.com/OCA/l10n-mexico/tree/13.0/l10n_mx_sat_account>`_ project on GitHub.

You are welcome to contribute. To learn how please visit https://odoo-community.org/page/Contribute.
