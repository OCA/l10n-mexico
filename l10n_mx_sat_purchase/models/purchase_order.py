# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    l10n_mx_sat_has_qty_to_bill = fields.Boolean(
        string="Has Quantities to Bill",
        compute="_compute_l10n_mx_sat_has_qty_to_bill",
        help="Some line has a positive quantity to bill. An order billed beyond "
        "its quantities is 'To Bill' for Odoo, but there is nothing to bill.",
    )

    l10n_mx_sat_has_bill_to_link = fields.Boolean(
        string="Has Bills to Link",
        compute="_compute_l10n_mx_sat_has_move_to_link",
        search="_search_l10n_mx_sat_has_bill_to_link",
        help="Some vendor bill of the order has no SAT CFDI linked yet.",
    )
    l10n_mx_sat_has_refund_to_link = fields.Boolean(
        string="Has Credit Notes to Link",
        compute="_compute_l10n_mx_sat_has_move_to_link",
        search="_search_l10n_mx_sat_has_refund_to_link",
        help="Some vendor credit note of the order has no SAT CFDI linked yet.",
    )

    @api.depends("order_line.qty_to_invoice")
    def _compute_l10n_mx_sat_has_qty_to_bill(self):
        for order in self:
            order.l10n_mx_sat_has_qty_to_bill = any(
                float_compare(
                    line.qty_to_invoice,
                    0,
                    precision_rounding=line.product_uom_id.rounding or 0.01,
                )
                > 0
                for line in order.order_line
            )

    @api.depends("invoice_ids.state", "invoice_ids.l10n_mx_sat_document_ids")
    def _compute_l10n_mx_sat_has_move_to_link(self):
        Move = self.env["account.move"]
        for order in self:
            for name, move_type in (
                ("l10n_mx_sat_has_bill_to_link", "in_invoice"),
                ("l10n_mx_sat_has_refund_to_link", "in_refund"),
            ):
                order[name] = bool(
                    Move.search_count(
                        Move._l10n_mx_sat_get_to_link_domain(move_type)
                        + [("id", "in", order.invoice_ids.ids)],
                        limit=1,
                    )
                )

    def _search_l10n_mx_sat_has_bill_to_link(self, operator, value):
        return self._l10n_mx_sat_search_move_to_link("in_invoice", operator)

    def _search_l10n_mx_sat_has_refund_to_link(self, operator, value):
        return self._l10n_mx_sat_search_move_to_link("in_refund", operator)

    def _l10n_mx_sat_search_move_to_link(self, move_type, operator):
        if operator != "in":
            # The ORM negates the domain for "not in"
            return NotImplemented
        domain = self.env["account.move"]._l10n_mx_sat_get_to_link_domain(move_type)
        return [("invoice_ids", "any", domain)]

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
