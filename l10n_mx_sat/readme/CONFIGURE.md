
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
6. Optionally set:
   - **Sync documents from**: earliest date of the first XML download.
     Leave it empty to download only the current month. One synchronization
     downloads at most one calendar month per document flow. Later runs
     continue from the last completed range.
   - **Automatic SAT download**: enable/disable daily cron processing.
     The daily job does not run when the module is installed. It starts
     only after FIEL credentials are stored.
7. Click **Test connection** to validate FIEL credentials.
8. Click **Sync now** to enqueue SAT XML download requests immediately.

Multi-company
-------------

Each company keeps its own FIEL credentials, download flow selection,
and sync windows. Users only see SAT documents and requests for
companies they are allowed to access.

Metadata
--------

Automatic metadata downloads are disabled for now. SAT status refresh
from metadata will be implemented in a later release.
