# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError


class L10nMxSatPurchaseInvoiceWizard(models.TransientModel):
    _name = "l10n_mx_sat.purchase.invoice.wizard"
    _inherit = "l10n_mx_sat.document.selector.mixin"
    _description = "Create the vendor bill of purchase orders from a SAT CFDI"

    purchase_order_ids = fields.Many2many(
        comodel_name="purchase.order",
        string="Purchase Orders",
        required=True,
    )
    partner_id = fields.Many2one(compute="_compute_from_orders")
    company_id = fields.Many2one(compute="_compute_from_orders")
    currency_id = fields.Many2one(compute="_compute_from_orders")
    amount_total = fields.Monetary(
        string="Orders Total", compute="_compute_from_orders"
    )
    line_ids = fields.One2many(
        comodel_name="l10n_mx_sat.purchase.invoice.wizard.line",
        inverse_name="wizard_id",
        string="SAT CFDIs",
    )
    l10n_mx_sat_document_id = fields.Many2one(
        compute="_compute_l10n_mx_sat_document_id"
    )
    total_mismatch = fields.Boolean(compute="_compute_total_mismatch")

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        order_ids = defaults.get("purchase_order_ids")
        if not order_ids or "line_ids" not in fields_list:
            return defaults
        wizard = self.new({"purchase_order_ids": order_ids})
        # Relational values of a new record are new records: keep the real ids
        documents = wizard.l10n_mx_sat_available_document_ids._origin
        matching = documents.filtered(
            lambda d: not wizard.currency_id.compare_amounts(
                d.total, wizard.amount_total
            )
        )
        defaults["line_ids"] = [
            Command.create(
                {
                    "document_id": document.id,
                    "selected": len(matching) == 1 and document == matching,
                }
            )
            for document in documents
        ]
        return defaults

    @api.depends("purchase_order_ids")
    def _compute_from_orders(self):
        for wizard in self:
            orders = wizard.purchase_order_ids
            wizard.partner_id = orders[:1].partner_id
            wizard.company_id = orders[:1].company_id
            wizard.currency_id = orders[:1].currency_id
            wizard.amount_total = sum(orders.mapped("amount_total"))

    @api.depends("line_ids.selected")
    def _compute_l10n_mx_sat_document_id(self):
        for wizard in self:
            selected = wizard.line_ids.filtered("selected")
            wizard.l10n_mx_sat_document_id = (
                selected.document_id if len(selected) == 1 else False
            )

    @api.depends("l10n_mx_sat_document_id", "amount_total")
    def _compute_total_mismatch(self):
        for wizard in self:
            document = wizard.l10n_mx_sat_document_id
            wizard.total_mismatch = bool(
                document
                and wizard.currency_id.compare_amounts(
                    document.total, wizard.amount_total
                )
            )

    @api.constrains("purchase_order_ids")
    def _check_purchase_order_ids(self):
        for wizard in self:
            orders = wizard.purchase_order_ids
            if (
                len(orders.partner_id.commercial_partner_id) > 1
                or len(orders.company_id) > 1
            ):
                raise ValidationError(
                    self.env._(
                        "The purchase orders must belong to the same vendor and company"
                    )
                )
            if len(orders.currency_id) > 1:
                raise ValidationError(
                    self.env._("The purchase orders must use the same currency.")
                )

    def _l10n_mx_sat_check_document(self):
        if len(self.line_ids.filtered("selected")) > 1:
            return self.env._(
                "Select only one CFDI: each bill comes from a single CFDI."
            )
        return super()._l10n_mx_sat_check_document()

    def action_create_invoice(self):
        self.ensure_one()
        rejection = self._l10n_mx_sat_check_document()
        if rejection:
            return self._l10n_mx_sat_rejection_action(rejection)
        orders = self.purchase_order_ids
        if orders.filtered(lambda o: o.state != "purchase"):
            raise UserError(self.env._("Only confirmed purchase orders can be billed."))
        document = self.l10n_mx_sat_document_id
        attachment = self.env["ir.attachment"].create(
            document._prepare_vendor_bill_attachment_vals()
        )
        invoices_before = orders.invoice_ids
        action = orders.action_create_invoice(attachment_ids=attachment.ids)
        move = orders.invoice_ids - invoices_before
        document._link_vendor_bill(move)
        return action


class L10nMxSatPurchaseInvoiceWizardLine(models.TransientModel):
    _name = "l10n_mx_sat.purchase.invoice.wizard.line"
    _description = "SAT CFDI proposed for the vendor bill of a purchase order"
    _order = "issue_date desc, id"

    wizard_id = fields.Many2one(
        comodel_name="l10n_mx_sat.purchase.invoice.wizard",
        required=True,
        ondelete="cascade",
    )
    document_id = fields.Many2one(
        comodel_name="l10n_mx_sat.document",
        string="SAT CFDI",
        required=True,
        readonly=True,
    )
    selected = fields.Boolean(string="Select")
    uuid = fields.Char(related="document_id.uuid")
    series = fields.Char(related="document_id.series")
    folio_number = fields.Char(related="document_id.folio_number")
    issuer_name = fields.Char(related="document_id.issuer_name")
    issue_date = fields.Datetime(related="document_id.issue_date")
    total = fields.Float(related="document_id.total")
    currency_code = fields.Char(related="document_id.currency_code")
    sat_status = fields.Selection(related="document_id.sat_status")
