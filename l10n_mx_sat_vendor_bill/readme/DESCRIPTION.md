This module creates draft vendor bills in Odoo Community from received
CFDIs stored by the ``l10n_mx_sat`` module after SAT bulk download.

Install ``satcfdi`` on the server (see ``l10n_mx_sat`` documentation) so
SAT web services can authenticate with FIEL credentials.

**Features:**

- Automatic vendor bill creation when received CFDI XML is downloaded
- Deduplication by CFDI UUID
- Tax matching (IVA, ISR, IEPS)
