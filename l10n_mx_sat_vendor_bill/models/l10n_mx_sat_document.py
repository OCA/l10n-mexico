# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class L10nMxSatDocument(models.Model):
    _inherit = "l10n_mx_sat.document"

    vendor_bill_id = fields.Many2one(
        comodel_name="account.move",
        string="Vendor bill",
        readonly=True,
        copy=False,
    )

    @api.model
    def _upsert_from_xml(self, tree, xml_bytes, company, request):
        document = super()._upsert_from_xml(tree, xml_bytes, company, request)
        if not document:
            return document
        if (
            request.document_kind != "cfdi"
            or request.direction != "received"
            or request.request_type != "xml"
        ):
            return document
        move = self.env["account.move"]._l10n_mx_sat_create_bill_from_cfdi(
            tree, xml_bytes, request
        )
        if move:
            document._sat_write({"vendor_bill_id": move.id})
        return document
