
For each Mexican company:

1. Open **Settings > Companies > [Company] > SAT** tab.
2. Click **Update FIEL credentials** and upload the certificate (`.cer`),
   private key (`.key`), and password in the wizard. The company VAT/RFC
   is set automatically from the FIEL certificate.
3. Once FIEL is configured, the company VAT/RFC becomes read-only and must
   be updated through the FIEL credentials wizard.
4. Review the FIEL configured indicator shown on the company form. Saved
   credentials are never displayed or downloadable from the UI.
5. Choose which XML download flows are enabled:
   - CFDI issued
   - CFDI received
   - Retentiones issued
   - Retentiones received
5. Optionally set:
   - **Sync documents from**: first XML backfill date.
   - **Automatic SAT download**: enable/disable daily cron processing.
6. Click **Test connection** to validate FIEL credentials.
7. Click **Sync now** to enqueue SAT XML download requests immediately.

Multi-company
-------------

Each company keeps its own FIEL credentials, download flow selection,
and sync windows. Users only see SAT documents and requests for
companies they are allowed to access.

Metadata
--------

Automatic metadata downloads are disabled for now. SAT status refresh
from metadata will be implemented in a later release.
