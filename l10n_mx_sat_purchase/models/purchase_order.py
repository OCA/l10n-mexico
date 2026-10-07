# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def action_l10n_mx_sat_select_document(self):
        companies = self.company_id.filtered(lambda c: not (c.vat or "").strip())
        if companies:
            raise UserError(
                self.env._(
                    "Set the RFC of %(company)s to bill from the CFDIs it received.",
                    company=", ".join(companies.mapped("name")),
                )
            )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Bill from SAT CFDI"),
            "res_model": "l10n_mx_sat.purchase.invoice.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_purchase_order_ids": self.ids},
        }
