# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # Searched to know whether a bill has a SAT CFDI: the search bypasses the
    # record rules, a buyer may not read every CFDI linked to a bill.
    l10n_mx_sat_document_ids = fields.One2many(
        comodel_name="l10n_mx_sat.document",
        inverse_name="vendor_bill_id",
        string="SAT CFDIs",
        bypass_search_access=True,
    )

    @api.model
    def _l10n_mx_sat_get_to_link_domain(self, move_type):
        """Domain of the vendor bills (or credit notes) of ``move_type`` that a
        SAT CFDI can still be linked to."""
        return [
            ("move_type", "=", move_type),
            ("state", "!=", "cancel"),
            ("l10n_mx_sat_document_ids", "=", False),
        ]
