# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def action_l10n_mx_sat_select_document(self):
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Bill from SAT CFDI"),
            "res_model": "l10n_mx_sat.purchase.invoice.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_purchase_order_ids": self.ids},
        }
