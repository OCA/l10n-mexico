# Copyright (C) 2026 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class Waybill(models.Model):
    _inherit = "l10n_mx_cfdi_waybill.waybill"

    tms_order_id = fields.Many2one("tms.order", string="Trip", ondelete="set null")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if self.env.context.get("active_model") != "tms.order":
            return values
        trip = self.env["tms.order"].browse(self.env.context.get("active_id"))
        if trip:
            values["tms_order_id"] = trip.id
        return values

    def _format_invoice_item_data(self, entry):
        cargo = entry.cargo_id
        if not cargo:
            return super()._format_invoice_item_data(entry)
        return {
            "ProductCode": cargo.l10n_mx_cfdi_product_code_id.code,
            "UnitCode": cargo.l10n_mx_cfdi_unit_id.code,
            "Description": cargo.name,
            "Quantity": entry.product_qty or cargo.quantity,
            "UnitPrice": 0,
            "Subtotal": 0,
            "Total": 0,
            "TaxObject": "01",
        }

    def _format_goods_transport_details(
        self, entry_id, origin_locations_codes, destination_locations_codes
    ):
        cargo = entry_id.cargo_id
        if not cargo:
            return super()._format_goods_transport_details(
                entry_id, origin_locations_codes, destination_locations_codes
            )
        origin_location_id = origin_locations_codes[entry_id.origin_address_id]
        destination_location_id = destination_locations_codes[
            entry_id.destination_address_id
        ]
        quantity = entry_id.product_qty or cargo.quantity
        data = {
            "Cantidad": quantity,
            "BienesTransp": cargo.l10n_mx_cfdi_product_code_id.code,
            "Descripcion": cargo.name,
            "ClaveUnidad": cargo.l10n_mx_cfdi_unit_id.code,
            "PesoEnKg": f"{cargo._l10n_mx_cfdi_weight_kg():.3f}",
            "CantidadTransporta": [
                {
                    "Cantidad": quantity,
                    "IDOrigen": origin_location_id,
                    "IDDestino": destination_location_id,
                }
            ],
        }
        if cargo.l10n_mx_cfdi_hazardous:
            data["MaterialPeligroso"] = "Sí"
            if cargo.l10n_mx_cfdi_hazardous_code:
                data["CveMaterialPeligroso"] = cargo.l10n_mx_cfdi_hazardous_code
            if cargo.l10n_mx_cfdi_sat_packaging:
                data["Embalaje"] = cargo.l10n_mx_cfdi_sat_packaging
        if cargo.l10n_mx_cfdi_declared_value:
            currency = self.env.company.currency_id
            data["ValorMercancia"] = f"{cargo.l10n_mx_cfdi_declared_value:.2f}"
            data["Moneda"] = currency.name or "MXN"
        return data
