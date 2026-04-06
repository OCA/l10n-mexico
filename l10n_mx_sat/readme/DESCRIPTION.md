Base module to connect Odoo to the Mexican Tax Administration (SAT)
portal using FIEL electronic signature credentials.

It provides:

- Fields to store the FIEL certificate (.cer), private key (.key) and
  password on the company configuration.
- A button to test the connection to the SAT.
- An adapter (`SatClient`) that wraps communication with the SAT via
  the `cfdiclient` library. Other modules can use this adapter without
  depending directly on `cfdiclient`.
- A factory method `company.l10n_mx_sat_get_client()` that returns an
  adapter instance. It can be overridden via `_inherit` to swap the
  underlying implementation.

This module does NOT perform any business operation on its own. It is
a base for modules such as `l10n_mx_sat_vendor_bill` that download
invoices from the SAT.
