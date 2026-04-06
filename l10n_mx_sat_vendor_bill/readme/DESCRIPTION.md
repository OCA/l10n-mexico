This module downloads vendor bills (CFDIs recibidos) from the Mexican Tax
Administration (SAT) using the Descarga Masiva web service and creates
draft vendor bills in Odoo Community.

It uses the ``cfdiclient`` library to authenticate with FIEL credentials
and communicate with SAT's SOAP endpoints.

**Features:**

- Automatic download via scheduled action (every 6 hours)
- Manual "Sync Now" button in Accounting Settings
- Configurable start date for initial sync
- State machine for async SAT request processing
- Deduplication by CFDI UUID
- Tax matching (IVA, ISR, IEPS)
