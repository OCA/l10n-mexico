# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import _, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_mx_sat_vendor_bill_sync_from = fields.Date(
        related="company_id.l10n_mx_sat_vendor_bill_sync_from",
        readonly=False,
    )
    l10n_mx_sat_vendor_bill_last_sync = fields.Datetime(
        related="company_id.l10n_mx_sat_vendor_bill_last_sync",
    )

    def l10n_mx_sat_vendor_bill_sync_now(self):
        """Manual trigger for vendor bill sync."""
        self.env["l10n_mx_sat.download.request"].with_context(
            l10n_mx_sat_vendor_bill_manual_sync=True
        )._cron_process_requests(companies=self.company_id)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("SAT Vendor Bill Sync"),
                "message": _(
                    "Sync initiated. Open SAT Download Requests to follow progress. "
                    "Note: “Sync from date” applies only until the first successful "
                    "download; after that, each new request continues from the last "
                    "completed period (it does not reset to that date)."
                ),
                "type": "info",
                "sticky": True,
            },
        }
