# Copyright (C) 2026 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_mx_cfdi_tms_waybill_id = fields.Many2one(
        "l10n_mx_cfdi_waybill.waybill",
        string="Carta Porte",
        compute="_compute_l10n_mx_cfdi_tms_waybill_id",
        store=True,
        readonly=False,
    )

    def _l10n_mx_cfdi_tms_waybills(self):
        self.ensure_one()
        lines = self.invoice_line_ids.sale_line_ids
        trips = lines.tms_order_ids | lines.cargo_ids.order_id
        return trips.waybill_ids.filtered(lambda waybill: waybill.state != "canceled")

    @api.depends(
        "invoice_line_ids.sale_line_ids.tms_order_ids.waybill_ids.state",
        "invoice_line_ids.sale_line_ids.cargo_ids.order_id.waybill_ids.state",
    )
    def _compute_l10n_mx_cfdi_tms_waybill_id(self):
        for move in self:
            waybills = move._l10n_mx_cfdi_tms_waybills()
            current = move.l10n_mx_cfdi_tms_waybill_id
            if len(waybills) == 1:
                move.l10n_mx_cfdi_tms_waybill_id = waybills
            elif current not in waybills:
                move.l10n_mx_cfdi_tms_waybill_id = False

    def _l10n_mx_cfdi_invoice_exportacion_complemento(self):
        exportacion, complemento = (
            super()._l10n_mx_cfdi_invoice_exportacion_complemento()
        )
        waybill = self.l10n_mx_cfdi_tms_waybill_id
        if not waybill:
            return exportacion, complemento
        from odoo.addons.l10n_mx_cfdi_waybill.services.waybill_builder import (
            build_carta_porte_from_dict,
        )

        carta_data = waybill._format_data()["Complemento"]["CartaPorte31"]
        carta = build_carta_porte_from_dict(carta_data)
        if complemento is None:
            return exportacion, carta
        if isinstance(complemento, list):
            return exportacion, [*complemento, carta]
        return exportacion, [complemento, carta]
