# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_mx_sat_vendor_bill_sync_from = fields.Date(
        string="Sync Vendor Bills From",
        help="First-time lower bound for the date range sent to SAT (inclusive). "
        "If there is already at least one *completed* SAT download request for this "
        "company, new requests continue from the end of the last successful range; "
        "this date is then ignored until you have no completed requests (e.g. after "
        "deleting or archiving them). Leave empty to default the first sync to the "
        "last 30 days.",
    )
    l10n_mx_sat_vendor_bill_last_sync = fields.Datetime(
        string="Last Vendor Bill Sync",
        readonly=True,
    )
