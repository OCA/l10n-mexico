Description
===========

Base module to connect Odoo to the Mexican Tax Administration (SAT)
portal using FIEL electronic signature credentials.

It provides:

- Multi-company FIEL credentials stored on each `res.company` record.
- A SAT tab on the company form to configure download flows, sync dates,
  and manual synchronization.
- A secure FIEL credentials wizard that stores certificate, key, and
  password without exposing saved values in the UI.
- Generic SAT document storage (`l10n_mx_sat.document`) for CFDIs and
  retentions, both issued and received.
- A download orchestration layer (`l10n_mx_sat.download.request`) that
  handles XML mass downloads via `satcfdi`.
- Configurable XML download flows per company: CFDI issued/received and
  retentions issued/received.
- An adapter (`SatClient`) that wraps communication with the SAT via
  the `satcfdi` library. Other modules can use this adapter without
  depending directly on `satcfdi`.
- A factory method `company.l10n_mx_sat_get_client()` that returns an
  adapter instance. It can be overridden via `_inherit` to swap the
  underlying implementation.


This module downloads and stores SAT XML documents. Automatic metadata
synchronization is postponed for a future release. Other custom modules
may consume `l10n_mx_sat.document` records for their own business flows.
